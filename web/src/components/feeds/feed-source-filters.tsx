import { Collapse, Group, Input, SegmentedControl } from "@mantine/core";
import { useTranslation } from "react-i18next";
import type { FeedSourceFilters, FeedSourceTriFilter } from "@/lib/feeds/groups";

function parseTri(value: string): FeedSourceTriFilter | undefined {
  if (value === "true" || value === "false") {
    return value;
  }
  return undefined;
}

function TriFilterControl({
  label,
  value,
  trueLabel,
  falseLabel,
  onChange,
}: {
  label: string;
  value: FeedSourceTriFilter | undefined;
  trueLabel: string;
  falseLabel: string;
  onChange: (next: FeedSourceTriFilter | undefined) => void;
}) {
  const { t } = useTranslation("feeds");
  return (
    <Input.Wrapper label={label} size="sm">
      <SegmentedControl
        size="sm"
        value={value ?? "any"}
        onChange={(next) => onChange(parseTri(next))}
        data={[
          { value: "any", label: t("filter.any") },
          { value: "true", label: trueLabel },
          { value: "false", label: falseLabel },
        ]}
      />
    </Input.Wrapper>
  );
}

export function FeedSourceFilterControls({
  opened,
  values,
  onChange,
}: {
  opened: boolean;
  values: FeedSourceFilters;
  onChange: (next: FeedSourceFilters) => void;
}) {
  const { t } = useTranslation("feeds");
  return (
    <Collapse expanded={opened}>
      <Group gap="lg" align="flex-end" wrap="wrap">
        <TriFilterControl
          label={t("fields.enabled")}
          value={values.enabled}
          trueLabel={t("filter.enabled")}
          falseLabel={t("filter.disabled")}
          onChange={(enabled) => onChange({ ...values, enabled })}
        />
        <TriFilterControl
          label={t("fields.autoEnqueue")}
          value={values.auto_enqueue}
          trueLabel={t("filter.autoEnqueue")}
          falseLabel={t("filter.discoverOnly")}
          onChange={(auto_enqueue) => onChange({ ...values, auto_enqueue })}
        />
      </Group>
    </Collapse>
  );
}
