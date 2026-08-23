import {
  Alert,
  Anchor,
  Badge,
  Breadcrumbs,
  Button,
  Group,
  Loader,
  Stack,
  Title,
} from "@mantine/core";
import { IconAlertCircle, IconFilter } from "@tabler/icons-react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { getFacetOptions, listMetadataInfiniteOptions } from "@/client/@tanstack/react-query.gen";
import type { FacetKind } from "@/client/types.gen";
import { InfiniteScrollSentinel } from "@/components/common/infinite-scroll-sentinel";
import { PosterGrid } from "@/components/media/poster-grid";
import { isOneOf } from "@/lib/exhaustive";
import { CATALOG_FACET_KINDS } from "@/lib/exhaustive-maps";
import { FACET_FILTER_PARAM, metaSearchForFacet } from "@/lib/facets";
import { nextOffsetPageParam } from "@/lib/infinite-list";

const CHUNK = 30;

export const Route = createFileRoute("/catalog/$kind_/$facetId")({
  component: FacetDetailPage,
});

function FacetDetailPage() {
  const { kind: rawKind, facetId } = Route.useParams();
  const { t } = useTranslation(["metadata", "common"]);

  const id = Number(facetId);
  const validId = Number.isInteger(id) && id > 0;
  const validKind = isOneOf(CATALOG_FACET_KINDS, rawKind);
  const kind: FacetKind = validKind ? rawKind : "tag";
  const param = FACET_FILTER_PARAM[kind];

  const { data: facet, isLoading: facetLoading } = useQuery({
    ...getFacetOptions({ path: { kind, facet_id: id } }),
    enabled: validKind && validId,
  });
  const { data, isLoading, hasNextPage, isFetchingNextPage, fetchNextPage } = useInfiniteQuery({
    ...listMetadataInfiniteOptions({
      query: { limit: CHUNK, [param]: id },
    }),
    enabled: validKind && validId,
    initialPageParam: 0,
    getNextPageParam: nextOffsetPageParam,
  });

  const items = useMemo(() => data?.pages.flatMap((p) => p.items) ?? [], [data]);
  const total = data?.pages[0]?.total ?? 0;

  if (!validKind || !validId) {
    return (
      <Alert color="red" icon={<IconAlertCircle size={18} />}>
        {t("common:status.error")}
      </Alert>
    );
  }

  return (
    <Stack gap="md">
      <Breadcrumbs>
        <Anchor component={Link} to="/catalog" size="sm">
          {t("browse.title")}
        </Anchor>
        <Link to="/catalog/$kind" params={{ kind }} style={{ textDecoration: "none" }}>
          <Anchor component="span" size="sm">
            {t(`browse.kinds.${kind}`)}
          </Anchor>
        </Link>
      </Breadcrumbs>

      <Group gap="sm" align="center" justify="space-between" wrap="wrap">
        <Group gap="sm" align="center">
          {facetLoading ? <Loader size="sm" /> : <Title order={2}>{facet?.name}</Title>}
          {facet && (
            <Badge size="lg" variant="light">
              {t("browse.count", { count: facet.count })}
            </Badge>
          )}
        </Group>
        <Link to="/meta" search={metaSearchForFacet(kind, id)} style={{ textDecoration: "none" }}>
          <Button variant="light" size="sm" leftSection={<IconFilter size={14} />} component="span">
            {t("browse.filterInMeta")}
          </Button>
        </Link>
      </Group>

      <PosterGrid
        items={items}
        loading={isLoading && items.length === 0}
        emptyMessage={t("empty")}
      />

      {items.length > 0 && (
        <InfiniteScrollSentinel
          hasNextPage={Boolean(hasNextPage)}
          isFetchingNextPage={isFetchingNextPage}
          fetchNextPage={() => void fetchNextPage()}
          loadedLabel={t("common:pagination.loadedOfTotal", { loaded: items.length, total })}
        />
      )}
    </Stack>
  );
}
