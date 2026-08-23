import { Box, Group, Table, Text, UnstyledButton } from "@mantine/core";
import { IconChevronDown, IconChevronUp, IconSelector } from "@tabler/icons-react";
import type { MouseEvent as ReactMouseEvent, ReactNode } from "react";

interface ResizeHandleProps {
  onMouseDown: (event: ReactMouseEvent) => void;
  onDoubleClick: () => void;
}

interface SortableThProps<T extends string> {
  label: string;
  field: T;
  sortBy: T | undefined;
  order: "asc" | "desc" | undefined;
  onSort: (field: T) => void;
  w?: number | string;
  /** 列宽拖拽柄; 传入后 th 相对定位并渲染右侧把手. */
  resizeHandle?: ResizeHandleProps;
}

function ColumnResizeHandle({ onMouseDown, onDoubleClick }: ResizeHandleProps) {
  return (
    <Box
      component="span"
      onMouseDown={onMouseDown}
      onDoubleClick={onDoubleClick}
      style={{
        position: "absolute",
        top: 0,
        right: 0,
        bottom: 0,
        width: 6,
        cursor: "col-resize",
        touchAction: "none",
        userSelect: "none",
        zIndex: 1,
      }}
    />
  );
}

/** 可点击排序的表头; 当前列加粗并显示升降序指示. 可选右侧拖拽调宽. */
export function SortableTh<T extends string>({
  label,
  field,
  sortBy,
  order,
  onSort,
  w,
  resizeHandle,
}: SortableThProps<T>) {
  const active = sortBy === field;
  const Icon = !active ? IconSelector : order === "asc" ? IconChevronUp : IconChevronDown;

  return (
    <Table.Th w={w} pos={resizeHandle ? "relative" : undefined} style={{ overflow: "hidden" }}>
      <UnstyledButton onClick={() => onSort(field)} style={{ display: "block", width: "100%" }}>
        <Group gap={4} wrap="nowrap" style={{ minWidth: 0 }}>
          <Text span size="sm" fw={active ? 700 : 500} truncate>
            {label}
          </Text>
          <Icon size={14} stroke={1.5} style={{ flexShrink: 0 }} />
        </Group>
      </UnstyledButton>
      {resizeHandle && <ColumnResizeHandle {...resizeHandle} />}
    </Table.Th>
  );
}

interface StaticThProps {
  children: ReactNode;
  w?: number | string;
  ta?: "left" | "right" | "center";
  resizeHandle?: ResizeHandleProps;
}

/** 不可排序表头, 可选列宽拖拽. */
export function ResizableTh({ children, w, ta, resizeHandle }: StaticThProps) {
  return (
    <Table.Th
      w={w}
      ta={ta}
      pos={resizeHandle ? "relative" : undefined}
      style={{ overflow: "hidden" }}
    >
      {children}
      {resizeHandle && <ColumnResizeHandle {...resizeHandle} />}
    </Table.Th>
  );
}
