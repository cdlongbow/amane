import { getEffectiveType, isNullable } from "./schema/guards";
import type { JSONSchemaObject } from "./schema/types";

/** OpenAPI / JSON Schema 对象 (含 hey-api `as const` 生成物). */
export type FormValueSchema = {
  readonly properties?: Readonly<Record<string, unknown>>;
};

function isSchemaObject(value: unknown): value is JSONSchemaObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * 按 **列/Create schema** 把表单空值编成 API 值. 不要对着 PATCH partial schema 编码
 * (create_partial_model 会把非空列也标成 T|null, 空 glob 会被编成 JSON null).
 *
 * - 键值为 `undefined`: 省略 (调用方不应写入 body)
 * - 空串 + 可空 string: `null`
 * - 空串 + 非空 string: `""`
 * - 空数组 / `null` 落到非空 array: `[]`
 * - 可空字段上的 `null`: 保持 `null`
 */
export function encodeEmptyValue(schema: unknown, value: undefined): undefined;
export function encodeEmptyValue(schema: unknown, value: string): string | null;
export function encodeEmptyValue<T>(schema: unknown, value: T): T;
export function encodeEmptyValue(schema: unknown, value: unknown): unknown {
  if (value === undefined) {
    return undefined;
  }
  const field = isSchemaObject(schema) ? schema : undefined;
  if (typeof value === "string" && value.trim() === "") {
    return field != null && isNullable(field) ? null : "";
  }
  if (value === null && field != null) {
    const effective = getEffectiveType(field);
    if (effective.type === "array" && !isNullable(field)) {
      return [];
    }
  }
  return value;
}

/** 逐字段 `encodeEmptyValue`; `undefined` 键不出现在结果里. */
export function encodeFormBody(
  schema: FormValueSchema,
  values: Record<string, unknown>,
): Record<string, unknown> {
  const props = schema.properties ?? {};
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined) {
      continue;
    }
    out[key] = encodeEmptyValue(props[key], value);
  }
  return out;
}
