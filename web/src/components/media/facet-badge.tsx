import { Badge, type MantineColor } from "@mantine/core";
import { Link } from "@tanstack/react-router";
import type { FacetKind } from "@/client/types.gen";
import { metaSearchForFacet } from "@/lib/facets";

const KIND_COLOR: Record<FacetKind, MantineColor> = {
  actor: "grape",
  director: "indigo",
  tag: "teal",
  studio: "blue",
  publisher: "cyan",
  series: "orange",
  user_tag: "pink",
};

interface FacetBadgeProps {
  kind: FacetKind;
  /** Facet id - 未知 (未建立投影索引) 时为 null/undefined, 渲染为不可点击的纯文本徽章. */
  id: number | null | undefined;
  name: string;
  /** "catalog": 分类实体页 (actor → /actors/$id); "meta": 片库列表并附带该 facet 过滤. @default "catalog" */
  mode?: "meta" | "catalog";
  variant?: "filled" | "light" | "outline" | "dot" | "transparent";
  size?: "xs" | "sm" | "md" | "lg";
}

/** 默认为实体页; `mode="meta"` 时进入片库筛选. */
export function FacetBadge({
  kind,
  id,
  name,
  mode = "catalog",
  variant = "light",
  size = "sm",
}: FacetBadgeProps) {
  const color = KIND_COLOR[kind];

  if (id == null) {
    return (
      <Badge color={color} variant={variant} size={size}>
        {name}
      </Badge>
    );
  }

  if (mode === "catalog") {
    if (kind === "actor") {
      return (
        <Link
          to="/actors/$actorId"
          params={{ actorId: String(id) }}
          style={{ textDecoration: "none" }}
        >
          <Badge
            component="span"
            color={color}
            variant={variant}
            size={size}
            style={{ cursor: "pointer" }}
          >
            {name}
          </Badge>
        </Link>
      );
    }
    return (
      <Link
        to="/catalog/$kind/$facetId"
        params={{ kind, facetId: String(id) }}
        style={{ textDecoration: "none" }}
      >
        <Badge
          component="span"
          color={color}
          variant={variant}
          size={size}
          style={{ cursor: "pointer" }}
        >
          {name}
        </Badge>
      </Link>
    );
  }

  return (
    <Link to="/meta" search={metaSearchForFacet(kind, id)} style={{ textDecoration: "none" }}>
      <Badge
        component="span"
        color={color}
        variant={variant}
        size={size}
        style={{ cursor: "pointer" }}
      >
        {name}
      </Badge>
    </Link>
  );
}
