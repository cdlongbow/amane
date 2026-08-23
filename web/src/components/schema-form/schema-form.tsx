import { Affix, Box, Button, Group, Paper, Stack, Text, Transition } from "@mantine/core";
import { useForm } from "@tanstack/react-form";
import { useCallback, useId, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { isRecord } from "@/lib/utils";
import { encodeFormBody } from "./encode";
import { FieldRouter } from "./fields";
import type { JSONSchemaObject } from "./schema";
import { createSchemaValidator } from "./schema";

/** Deep equality check for config values (handles primitives, arrays, objects). */
function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (a == null || b == null) return a === b;
  if (typeof a !== typeof b) return false;
  if (Array.isArray(a)) {
    if (!Array.isArray(b) || a.length !== b.length) return false;
    return a.every((v, i) => deepEqual(v, b[i]));
  }
  if (isRecord(a) && isRecord(b)) {
    const keysA = Object.keys(a);
    const keysB = Object.keys(b);
    if (keysA.length !== keysB.length) return false;
    return keysA.every((k) => deepEqual(a[k], b[k]));
  }
  return false;
}

interface SchemaFormProps {
  /**
   * The schema describing this form's fields. All $ref should be resolved.
   * Each entry in `schema.properties` is rendered as a field via FieldRouter.
   */
  schema: JSONSchemaObject;
  /**
   * Path prefix prepended to field names (e.g., "scraping").
   * Field names become `${prefix}.${fieldKey}`, matching the nested defaultValues structure.
   */
  prefix: string;
  /** Initial values scoped to this form's fields (flat key→value for each property in schema). */
  values: Record<string, unknown>;
  /** i18n lookup prefix: "namespace:pathPrefix" (e.g., "settings:fields"). */
  i18nPrefix: string;
  onSave: (patch: Record<string, unknown>) => void;
  saving: boolean;
  /**
   * Where dirty save/reset actions appear.
   * - `affix`: fixed viewport-bottom bar (settings page).
   * - `inline`: in-flow bar at the end of the form (modals / embedded).
   * @default "inline"
   */
  actionsPlacement?: "affix" | "inline";
  /**
   * - `patch` (default): dirty-gated save bar; `onSave` receives only changed fields.
   * - `create`: always-visible submit bar; `onSave` receives the full form values.
   */
  mode?: "patch" | "create";
  /** Override the primary action label (defaults: save / submit by mode). */
  submitLabel?: string;
  /** Extra disable gate for the primary action (e.g. parent envelope fields incomplete). */
  submitDisabled?: boolean;
}

export function SchemaForm({
  schema,
  prefix,
  i18nPrefix,
  values,
  onSave,
  saving,
  actionsPlacement = "inline",
  mode = "patch",
  submitLabel,
  submitDisabled = false,
}: SchemaFormProps) {
  const { t } = useTranslation("common");
  const formId = useId();
  const properties = useMemo(() => schema.properties ?? {}, [schema.properties]);
  const isCreate = mode === "create";

  // Build defaultValues as { [prefix]: { field1: val1, field2: val2, ... } }
  // TanStack Form resolves dot-path names like "prefix.field1" to this nested object.
  const defaultValues = useMemo(() => {
    const fields: Record<string, unknown> = {};
    for (const fieldKey of Object.keys(properties)) {
      const fieldSchema = properties[fieldKey];
      if (Object.prototype.hasOwnProperty.call(values, fieldKey)) {
        fields[fieldKey] = values[fieldKey];
      } else if (typeof fieldSchema !== "boolean" && "default" in fieldSchema) {
        fields[fieldKey] = fieldSchema.default;
      } else {
        fields[fieldKey] = null;
      }
    }
    return { [prefix]: fields };
  }, [prefix, properties, values]);

  // JSON Schema 约束校验器 - 投影逐字段错误到 TanStack Form 的 field.meta.errors.
  // i18next 的 t 只接受字面量 key, 校验消息 key 是动态拼接的, 故经 as never 适配
  // (与 use-schema-i18n.ts 的既有约定一致).
  const validate = useMemo(
    () =>
      createSchemaValidator(prefix, properties, (key, opts) =>
        String(t(key as never, opts as never)),
      ),
    [prefix, properties, t],
  );

  const form = useForm({
    defaultValues,
    validators: { onChange: validate },
    onSubmit: ({ value }) => {
      const sectionVal = isRecord(value) && isRecord(value[prefix]) ? value[prefix] : {};
      if (isCreate) {
        onSave(encodeFormBody(schema, { ...sectionVal }));
        return;
      }
      const patch: Record<string, unknown> = {};
      for (const [field, val] of Object.entries(sectionVal)) {
        if (!deepEqual(val, values[field] ?? null)) {
          patch[field] = val;
        }
      }
      if (Object.keys(patch).length > 0) {
        onSave(encodeFormBody(schema, patch));
      }
    },
  });

  const handleReset = useCallback(() => {
    form.reset(defaultValues);
  }, [form, defaultValues]);

  const primaryLabel =
    submitLabel ??
    (isCreate ? t("actions.submit") : saving ? t("actions.saving") : t("actions.save"));

  const actions = (
    <form.Subscribe
      selector={(s) => {
        const current = isRecord(s.values) && isRecord(s.values[prefix]) ? s.values[prefix] : {};
        return {
          dirty: !deepEqual(current, values),
          isValid: s.isValid,
        };
      }}
    >
      {({ dirty, isValid }) => {
        if (isCreate) {
          const createBar = (
            <Group justify="flex-end">
              <Button
                type="submit"
                form={formId}
                disabled={saving || !isValid || submitDisabled}
                loading={saving}
              >
                {primaryLabel}
              </Button>
            </Group>
          );
          return <Box mt="md">{createBar}</Box>;
        }

        const bar = (
          <Paper withBorder shadow="md" px="md" py="sm" radius="md">
            <Group gap="md" wrap="nowrap" justify="space-between">
              <Text size="sm">{t("status.unsavedChanges")}</Text>
              <Group gap="sm" wrap="nowrap">
                <Button type="button" variant="default" onClick={handleReset} disabled={saving}>
                  {t("actions.discard")}
                </Button>
                {/* form= associates portaled Affix buttons with the <form> */}
                <Button
                  type="submit"
                  form={formId}
                  disabled={saving || !isValid || submitDisabled}
                  loading={saving}
                >
                  {saving ? t("actions.saving") : (submitLabel ?? t("actions.save"))}
                </Button>
              </Group>
            </Group>
          </Paper>
        );

        if (actionsPlacement === "affix") {
          return (
            <Affix position={{ bottom: 24, left: 0, right: 0 }} withinPortal>
              <Transition mounted={dirty} transition="slide-up" duration={180}>
                {(styles) => (
                  <Box
                    style={{
                      ...styles,
                      display: "flex",
                      justifyContent: "center",
                      pointerEvents: "none",
                      paddingInline: 16,
                    }}
                  >
                    <Box style={{ pointerEvents: "auto", maxWidth: 560, width: "100%" }}>{bar}</Box>
                  </Box>
                )}
              </Transition>
            </Affix>
          );
        }

        if (!dirty) return null;
        return <Box mt="md">{bar}</Box>;
      }}
    </form.Subscribe>
  );

  return (
    <Stack
      component="form"
      id={formId}
      gap="md"
      onSubmit={(e) => {
        e.preventDefault();
        form.handleSubmit();
      }}
    >
      <Stack gap={0}>
        {Object.entries(properties).map(([fieldKey, fieldSchema], idx) => {
          if (typeof fieldSchema === "boolean") return null;
          return (
            <Box
              key={fieldKey}
              style={
                idx === 0
                  ? undefined
                  : { borderTop: "1px solid var(--mantine-color-default-border)" }
              }
            >
              <FieldRouter
                name={`${prefix}.${fieldKey}`}
                schema={fieldSchema}
                form={form}
                i18nPrefix={i18nPrefix}
              />
            </Box>
          );
        })}
      </Stack>

      {actions}
    </Stack>
  );
}
