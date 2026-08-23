import {
  Button,
  Checkbox,
  Group,
  SegmentedControl,
  Stack,
  Switch,
  Text,
  TextInput,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  IconArchive,
  IconArchiveOff,
  IconArrowsDiagonal,
  IconArrowsDiagonalMinimize,
  IconRefresh,
  IconSearch,
  IconTrash,
} from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Virtuoso } from "react-virtuoso";
import {
  listAllFeedItemsOptions,
  listAllFeedItemsQueryKey,
  listFeedsQueryKey,
} from "@/client/@tanstack/react-query.gen";
import { batchFeedItems } from "@/client/sdk.gen";
import type {
  FeedItemBatchAction,
  FeedItemBatchResponse,
  FeedItemResponse,
  FeedItemState,
  FeedResponse,
} from "@/client/types.gen";
import { ListPagination } from "@/components/common/list-pagination";
import { PageSizeSelect } from "@/components/common/page-size-select";
import { SelectionBar } from "@/components/common/selection-bar";
import { useIdSelection } from "@/hooks/use-id-selection";
import { useResettingState } from "@/hooks/use-resetting-state";
import { extractErrorMessage } from "@/lib/api-error";
import { confirm } from "@/lib/confirm";
import { type DedupedFeedItem, dedupeFeedItems } from "@/lib/feeds/dedupe";
import { UNGROUPED_GROUP } from "@/lib/feeds/groups";
import { useUIStore } from "@/stores/ui";
import { FeedArticle } from "./feed-article";

function isFeedItemState(value: string): value is FeedItemState {
  return value === "active" || value === "ignored" || value === "all";
}

function emptyBatch(): FeedItemBatchResponse {
  return { affected: 0, missing: 0, skipped: 0, submitted: 0, task_ids: [] };
}

async function batchAcrossFeeds(
  items: readonly FeedItemResponse[],
  ids: readonly number[],
  action: FeedItemBatchAction,
): Promise<FeedItemBatchResponse> {
  const byId = new Map(items.map((item) => [item.id, item]));
  const grouped = new Map<number, number[]>();
  const totals = emptyBatch();
  for (const id of ids) {
    const item = byId.get(id);
    if (item == null) {
      totals.missing += 1;
      continue;
    }
    const list = grouped.get(item.feed_id);
    if (list == null) {
      grouped.set(item.feed_id, [id]);
    } else {
      list.push(id);
    }
  }
  for (const [feedId, feedIds] of grouped) {
    const { data } = await batchFeedItems({
      path: { feed_id: feedId },
      body: { action, ids: feedIds },
      throwOnError: true,
    });
    totals.affected += data.affected;
    totals.missing += data.missing;
    totals.skipped = (totals.skipped ?? 0) + (data.skipped ?? 0);
    totals.submitted = (totals.submitted ?? 0) + (data.submitted ?? 0);
    totals.task_ids = [...(totals.task_ids ?? []), ...(data.task_ids ?? [])];
  }
  return totals;
}

function FeedReaderRow({
  row,
  feed,
  expanded,
  selected,
  showFeedName,
  busy,
  onToggleExpand,
  onToggleSelect,
  onScrape,
  onIgnore,
  onUnignore,
  onDelete,
  onOpenFeed,
}: {
  row: DedupedFeedItem;
  feed: FeedResponse | undefined;
  expanded: boolean;
  selected: boolean;
  showFeedName: boolean;
  busy: boolean;
  onToggleExpand: (id: number) => void;
  onToggleSelect: (id: number) => void;
  onScrape: (id: number) => void;
  onIgnore: (id: number) => void;
  onUnignore: (id: number) => void;
  onDelete: (id: number) => void;
  onOpenFeed: (feed: FeedResponse) => void;
}) {
  return (
    <FeedArticle
      item={row.item}
      feed={feed}
      expanded={expanded}
      selected={selected}
      duplicateCount={row.duplicates.length}
      showFeedName={showFeedName}
      busy={busy}
      onToggleExpand={() => onToggleExpand(row.item.id)}
      onToggleSelect={() => onToggleSelect(row.item.id)}
      onScrape={() => onScrape(row.item.id)}
      onIgnore={() => onIgnore(row.item.id)}
      onUnignore={() => onUnignore(row.item.id)}
      onDelete={() => onDelete(row.item.id)}
      onOpenFeed={onOpenFeed}
    />
  );
}

export function FeedReader({
  feeds,
  feedId,
  group,
  q,
  state,
  page,
  dedupe,
  onQueryChange,
  onStateChange,
  onPageChange,
  onDedupeChange,
  onOpenFeed,
}: {
  feeds: readonly FeedResponse[];
  feedId: number | undefined;
  group: string | undefined;
  q: string | undefined;
  state: FeedItemState;
  page: number;
  dedupe: boolean;
  onQueryChange: (q: string | undefined) => void;
  onStateChange: (state: FeedItemState) => void;
  onPageChange: (page: number) => void;
  onDedupeChange: (dedupe: boolean) => void;
  onOpenFeed: (feed: FeedResponse) => void;
}) {
  const { t } = useTranslation(["feeds", "common"]);
  const queryClient = useQueryClient();
  const limit = useUIStore((s) => s.pageSizes.feedItems);
  const [searchInput, setSearchInput] = useResettingState(() => q ?? "", q);
  const [expanded, setExpanded] = useState<Set<number>>(() => new Set());
  const [collapsed, setCollapsed] = useState<Set<number>>(() => new Set());
  const [expandAll, setExpandAll] = useState(false);
  const { selected, selectedIds, toggleOne, toggleAll, isAllSelected, clear } = useIdSelection();

  const feedsById = useMemo(() => new Map(feeds.map((feed) => [feed.id, feed])), [feeds]);

  const itemQuery = useMemo(() => {
    const query: {
      offset: number;
      limit: number;
      state: FeedItemState;
      search?: string;
      feed_id?: number;
      group?: string;
    } = {
      offset: (page - 1) * limit,
      limit,
      state,
    };
    if (q != null && q !== "") {
      query.search = q;
    }
    if (feedId != null) {
      query.feed_id = feedId;
    } else if (group === UNGROUPED_GROUP) {
      query.group = "";
    } else if (group != null && group !== "") {
      query.group = group;
    }
    return query;
  }, [feedId, group, limit, page, q, state]);

  const { data, isLoading } = useQuery(listAllFeedItemsOptions({ query: itemQuery }));
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  const rows = useMemo(
    () =>
      dedupe
        ? dedupeFeedItems(data?.items ?? [])
        : (data?.items ?? []).map((item) => ({ item, duplicates: [] })),
    [dedupe, data?.items],
  );
  const visibleIds = rows.map((row) => row.item.id);
  const allSelected = isAllSelected(visibleIds);

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: listAllFeedItemsQueryKey() });
    void queryClient.invalidateQueries({ queryKey: listFeedsQueryKey() });
  }

  const batchMutation = useMutation({
    mutationFn: ({
      action,
      ids,
    }: {
      action: Exclude<FeedItemBatchAction, "scrape">;
      ids: number[];
    }) => batchAcrossFeeds(items, ids, action),
    onSuccess: (result) => {
      const message =
        result.missing > 0
          ? t("batchActionResultWithMissing", {
              affected: result.affected,
              missing: result.missing,
            })
          : t("batchActionResult", { affected: result.affected });
      notifications.show({ message, color: "blue" });
      clear();
      invalidate();
    },
    onError: (error) =>
      notifications.show({
        message: extractErrorMessage(error, t("common:toast.operationFailed")),
        color: "red",
      }),
  });
  const scrapeMutation = useMutation({
    mutationFn: (ids: number[]) => batchAcrossFeeds(items, ids, "scrape"),
    onSuccess: (result) => {
      notifications.show({
        message: t("scrapeBatchResult", {
          submitted: result.submitted,
          skipped: result.skipped,
          missing: result.missing,
        }),
        color: "blue",
      });
      clear();
      invalidate();
    },
    onError: (error) =>
      notifications.show({
        message: extractErrorMessage(error, t("common:toast.operationFailed")),
        color: "red",
      }),
  });

  const busy = scrapeMutation.isPending || batchMutation.isPending;
  const showIgnore = state !== "ignored";
  const showUnignore = state !== "active";

  function applySearch() {
    clear();
    onQueryChange(searchInput.trim() || undefined);
  }

  function changeState(next: string) {
    if (!isFeedItemState(next)) {
      return;
    }
    clear();
    onStateChange(next);
  }

  const deleteIds = useCallback(
    async (ids: number[]) => {
      if (ids.length === 0) {
        return;
      }
      const ok = await confirm({
        title: ids.length === 1 ? t("confirm.deleteItemTitle") : t("confirm.deleteItemsTitle"),
        message:
          ids.length === 1
            ? t("confirm.deleteItemMessage")
            : t("confirm.deleteItemsMessage", { count: ids.length }),
        confirmLabel: t("common:actions.delete"),
      });
      if (ok) {
        batchMutation.mutate({ action: "delete", ids });
      }
    },
    [batchMutation, t],
  );

  const toggleExpand = useCallback(
    (id: number) => {
      if (expandAll) {
        setCollapsed((prev) => {
          const next = new Set(prev);
          if (next.has(id)) {
            next.delete(id);
          } else {
            next.add(id);
          }
          return next;
        });
        return;
      }
      setExpanded((prev) => {
        const next = new Set(prev);
        if (next.has(id)) {
          next.delete(id);
        } else {
          next.add(id);
        }
        return next;
      });
    },
    [expandAll],
  );

  const renderItem = useCallback(
    (_index: number, row: DedupedFeedItem) => (
      <FeedReaderRow
        row={row}
        feed={feedsById.get(row.item.feed_id)}
        expanded={expandAll ? !collapsed.has(row.item.id) : expanded.has(row.item.id)}
        selected={selected.has(row.item.id)}
        showFeedName={feedId == null}
        busy={busy}
        onToggleExpand={toggleExpand}
        onToggleSelect={toggleOne}
        onScrape={(id) => scrapeMutation.mutate([id])}
        onIgnore={(id) => batchMutation.mutate({ action: "ignore", ids: [id] })}
        onUnignore={(id) => batchMutation.mutate({ action: "unignore", ids: [id] })}
        onDelete={(id) => void deleteIds([id])}
        onOpenFeed={onOpenFeed}
      />
    ),
    [
      batchMutation,
      busy,
      collapsed,
      deleteIds,
      expandAll,
      expanded,
      feedId,
      feedsById,
      onOpenFeed,
      scrapeMutation,
      selected,
      toggleExpand,
      toggleOne,
    ],
  );

  return (
    <Stack gap="sm" style={{ flex: 1, minHeight: 0, minWidth: 0 }}>
      <Group justify="space-between" wrap="wrap" align="flex-end">
        <Group gap="xs" wrap="wrap">
          <SegmentedControl
            value={state}
            onChange={changeState}
            data={[
              { value: "active", label: t("historyStates.active") },
              { value: "ignored", label: t("historyStates.ignored") },
              { value: "all", label: t("historyStates.all") },
            ]}
          />
          <TextInput
            value={searchInput}
            onChange={(event) => setSearchInput(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                applySearch();
              }
            }}
            onBlur={applySearch}
            placeholder={t("historySearchPlaceholder")}
            leftSection={<IconSearch size={16} />}
            w={240}
          />
          <Switch
            size="sm"
            checked={dedupe}
            onChange={(event) => onDedupeChange(event.currentTarget.checked)}
            label={t("reader.dedupe")}
          />
        </Group>
        <Group gap="xs">
          <Button
            size="xs"
            variant="light"
            leftSection={
              expandAll ? (
                <IconArrowsDiagonalMinimize size={14} />
              ) : (
                <IconArrowsDiagonal size={14} />
              )
            }
            onClick={() => {
              setExpandAll((prev) => !prev);
              setExpanded(new Set());
              setCollapsed(new Set());
            }}
          >
            {expandAll ? t("reader.collapseAll") : t("reader.expandAll")}
          </Button>
          <PageSizeSelect
            sizeKey="feedItems"
            onChanged={() => {
              clear();
              onPageChange(1);
            }}
          />
        </Group>
      </Group>

      <SelectionBar count={selectedIds.length}>
        {showIgnore && (
          <Button
            size="xs"
            variant="light"
            leftSection={<IconArchive size={14} />}
            loading={batchMutation.isPending}
            disabled={selectedIds.length === 0 || busy}
            onClick={() => batchMutation.mutate({ action: "ignore", ids: selectedIds })}
          >
            {t("actions.ignore")}
          </Button>
        )}
        {showUnignore && (
          <Button
            size="xs"
            variant="light"
            leftSection={<IconArchiveOff size={14} />}
            loading={batchMutation.isPending}
            disabled={selectedIds.length === 0 || busy}
            onClick={() => batchMutation.mutate({ action: "unignore", ids: selectedIds })}
          >
            {t("actions.unignore")}
          </Button>
        )}
        <Button
          size="xs"
          variant="light"
          color="red"
          leftSection={<IconTrash size={14} />}
          loading={batchMutation.isPending}
          disabled={selectedIds.length === 0 || busy}
          onClick={() => void deleteIds(selectedIds)}
        >
          {t("common:actions.delete")}
        </Button>
        <Button
          size="xs"
          variant="light"
          leftSection={<IconRefresh size={14} />}
          loading={scrapeMutation.isPending}
          disabled={selectedIds.length === 0 || busy}
          onClick={() => scrapeMutation.mutate(selectedIds)}
        >
          {t("actions.rescrape")}
        </Button>
      </SelectionBar>

      <Group gap="xs">
        <Checkbox
          checked={allSelected}
          disabled={visibleIds.length === 0 || busy}
          onChange={() => toggleAll(visibleIds)}
          label={t("reader.selectPage")}
        />
        <Text size="sm" c="dimmed">
          {t("reader.itemCount", { count: total })}
        </Text>
      </Group>

      <div style={{ flex: 1, minHeight: 0 }}>
        {!isLoading && rows.length === 0 ? (
          <Text c="dimmed" size="sm" ta="center" py="xl">
            {t("historyEmpty")}
          </Text>
        ) : (
          <Virtuoso
            style={{ height: "100%" }}
            data={rows}
            computeItemKey={(_index, row) => row.item.id}
            itemContent={renderItem}
          />
        )}
      </div>

      <Group justify="center">
        <ListPagination
          totalPages={totalPages}
          page={page}
          onChange={(next) => {
            clear();
            onPageChange(next);
          }}
        />
      </Group>
    </Stack>
  );
}
