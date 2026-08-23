import { Badge, Group, Stack, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { listFacetsOptions } from "@/client/@tanstack/react-query.gen";
import type { FacetKind } from "@/client/types.gen";
import { CATALOG_FACET_KINDS } from "@/lib/exhaustive-maps";
import { FACET_KIND_ICON } from "@/lib/facets";

export const Route = createFileRoute("/catalog/")({ component: CatalogIndexPage });

const PREVIEW = 36;

function KindSection({ kind }: { kind: Exclude<FacetKind, "actor"> }) {
  const { t } = useTranslation("metadata");
  const Icon = FACET_KIND_ICON[kind];
  const { data, isLoading } = useQuery(
    listFacetsOptions({ path: { kind }, query: { limit: PREVIEW, offset: 0 } }),
  );

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <Stack gap="sm">
      <Link
        to="/catalog/$kind"
        params={{ kind }}
        style={{ textDecoration: "none", color: "inherit", width: "fit-content" }}
      >
        <Group gap="xs" style={{ cursor: "pointer" }}>
          <Icon size={18} stroke={1.5} />
          <Text fw={600}>
            {t(`browse.kinds.${kind}`)}
            <Text span c="dimmed" fw={400} ml={6}>
              ({total})
            </Text>
          </Text>
        </Group>
      </Link>

      {isLoading && (
        <Text size="sm" c="dimmed">
          …
        </Text>
      )}

      <Group gap={8}>
        {items.map((facet) => (
          <Link
            key={facet.id}
            to="/catalog/$kind/$facetId"
            params={{ kind, facetId: String(facet.id) }}
            style={{ textDecoration: "none" }}
          >
            <Badge
              variant="light"
              radius="xl"
              size="md"
              style={{ textTransform: "none", cursor: "pointer" }}
            >
              {facet.name}
              <Text span c="dimmed" size="xs" ml={4}>
                ({facet.count})
              </Text>
            </Badge>
          </Link>
        ))}
        {total > items.length && (
          <Link to="/catalog/$kind" params={{ kind }} style={{ textDecoration: "none" }}>
            <Badge variant="outline" radius="xl" color="gray" style={{ cursor: "pointer" }}>
              +{total - items.length}
            </Badge>
          </Link>
        )}
      </Group>
    </Stack>
  );
}

function CatalogIndexPage() {
  const { t } = useTranslation("metadata");

  return (
    <Stack gap="xl">
      <div>
        <Title order={2}>{t("browse.title")}</Title>
        <Text c="dimmed" size="sm">
          {t("browse.subtitle")}
        </Text>
      </div>
      {CATALOG_FACET_KINDS.map((kind) => (
        <KindSection key={kind} kind={kind} />
      ))}
    </Stack>
  );
}
