/**
 * 片库列表的高级 facet 筛选: 展开后每个 kind 独立短搜索框, 选中即追加到 URL search.
 * 另含关联文件三态筛选 (不限 / 有 / 无).
 */

import { Collapse, Select, SimpleGrid, Stack, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { listFacetsOptions } from "@/client/@tanstack/react-query.gen";
import type { FacetKind } from "@/client/types.gen";
import { FACET_KINDS } from "@/lib/exhaustive-maps";
import { facetIdsOf, type FacetFilters } from "@/lib/facets";

const PICKER_LIMIT = 40;

/** URL / 控件用的关联文件三态; null = 不限. */
export type HasFilesFilter = boolean | null;

interface FacetFilterControlsProps {
  /** 是否展开高级筛选表单. */
  opened: boolean;
  /** 当前已激活的过滤参数; 已选同一实体时禁用对应选项. */
  filters: FacetFilters;
  onSelect: (kind: FacetKind, id: number) => void;
  /** 当前关联文件筛选; null = 不限. */
  hasFiles: HasFilesFilter;
  onHasFilesChange: (value: HasFilesFilter) => void;
}

function KindFacetPicker({
  kind,
  filters,
  onSelect,
  enabled,
}: {
  kind: FacetKind;
  filters: FacetFilters;
  onSelect: (kind: FacetKind, id: number) => void;
  enabled: boolean;
}) {
  const { t } = useTranslation("metadata");
  const [search, setSearch] = useState("");

  const { data, isFetching } = useQuery({
    ...listFacetsOptions({
      path: { kind },
      query: { search: search || undefined, limit: PICKER_LIMIT, offset: 0 },
    }),
    enabled,
  });

  const selected = new Set(facetIdsOf(filters, kind));
  const options = (data?.items ?? []).map((facet) => ({
    value: String(facet.id),
    label: `${facet.name} (${facet.count})`,
    disabled: selected.has(facet.id),
  }));

  return (
    <Select
      label={t(`browse.kinds.${kind}`)}
      placeholder={t("search.facetPlaceholder")}
      data={options}
      value={null}
      searchable
      searchValue={search}
      onSearchChange={setSearch}
      nothingFoundMessage={isFetching ? "…" : t("search.facetEmpty")}
      onChange={(v) => {
        if (v == null) return;
        const id = Number(v);
        if (!Number.isInteger(id) || id <= 0) return;
        onSelect(kind, id);
        setSearch("");
      }}
      clearable
      size="sm"
    />
  );
}

function hasFilesSelectValue(hasFiles: HasFilesFilter): string | null {
  if (hasFiles === true) return "true";
  if (hasFiles === false) return "false";
  return null;
}

export function FacetFilterControls({
  opened,
  filters,
  onSelect,
  hasFiles,
  onHasFilesChange,
}: FacetFilterControlsProps) {
  const { t } = useTranslation("metadata");

  return (
    <Collapse expanded={opened}>
      <Stack gap="xs">
        <Text size="sm" c="dimmed">
          {t("search.advancedHint")}
        </Text>
        <SimpleGrid cols={{ base: 1, xs: 2, sm: 3, md: 4 }} spacing="sm">
          {FACET_KINDS.map((kind) => (
            <KindFacetPicker
              key={kind}
              kind={kind}
              filters={filters}
              onSelect={onSelect}
              enabled={opened}
            />
          ))}
          <Select
            label={t("search.hasFiles")}
            placeholder={t("search.hasFilesAny")}
            data={[
              { value: "true", label: t("search.hasFilesYes") },
              { value: "false", label: t("search.hasFilesNo") },
            ]}
            value={hasFilesSelectValue(hasFiles)}
            onChange={(v) => {
              if (v === "true") onHasFilesChange(true);
              else if (v === "false") onHasFilesChange(false);
              else onHasFilesChange(null);
            }}
            clearable
            size="sm"
          />
        </SimpleGrid>
      </Stack>
    </Collapse>
  );
}
