/**
 * Extended JSON Schema types for Amane with x-* extensions.
 * Uses discriminated unions with per-type extensions.
 */

// ==================== Extension interfaces ====================

/** Widget types supported by the schema form system */
export type AmaneWidget = "PathPicker" | "LibraryPicker" | string;

/** 所有 schema 共享的基础扩展 */
export interface AmaneBaseExtensions {
  /** 自定义组件 */
  "x-widget"?: AmaneWidget;
  /** 隐藏该字段, 不在表单中渲染 */
  "x-hidden"?: boolean;
  /** 只读字段, 禁止编辑 */
  "x-readonly"?: boolean;
  /**
   * 在 dict 上下文中, 仅当 key 匹配时显示此子字段
   * @example "x-visible-keys": ["title", "plot"] → 仅在这些 key 下渲染
   */
  "x-visible-keys"?: string[];
  /** 在指定 key 下隐藏此子字段 */
  "x-hidden-keys"?: string[];
}

/** 文本字段扩展 - 仅用于 type: "string" (非 enum, 非 path) */
export interface AmaneTextExtensions extends AmaneBaseExtensions {
  /**
   * 多行文本输入
   * @example
   * // Pydantic: Field(json_schema_extra={"x-multiline": True})
   * { "type": "string", "x-multiline": true }
   */
  "x-multiline"?: boolean;
  /**
   * 长文本: 渲染为更高的多行文本框 (即使未设置 x-multiline), 适合正文/日志等长内容.
   * @example
   * // Pydantic: Field(json_schema_extra={"x-long": True})
   */
  "x-long"?: boolean;
}

/** 路径字段扩展 - 仅用于 x-widget: "PathPicker" 的 string 字段 */
export interface AmanePathExtensions extends AmaneBaseExtensions {
  "x-widget": "PathPicker";
  /**
   * 路径类型
   * - file: 只选文件
   * - directory: 只选目录
   * - mixed: 均可
   * @default "mixed"
   */
  "x-path-type"?: "file" | "directory" | "mixed";
}

/** 枚举字段扩展 - 仅用于有 enum 属性的字段 */
export interface AmaneEnumExtensions extends AmaneBaseExtensions {
  /**
   * 枚举值的显示名称, 与 enum 数组一一对应
   * @example
   * // enum: ["move", "copy", "hardlink"]
   * // x-show-names: ["移动", "复制", "硬链接"]
   */
  "x-show-names"?: string[];
  /**
   * 使用 toggle/radio 组件而非下拉框 (适合 ≤5 项)
   * @example
   * // Pydantic: Field(json_schema_extra={"x-simple": True})
   */
  "x-simple"?: boolean;
}

/** 数组字段扩展 - 仅用于 type: "array" */
export interface AmaneArrayExtensions extends AmaneBaseExtensions {
  /**
   * 有序数组: 显示拖拽手柄, 用户可调整顺序
   * 典型场景: 站点优先级列表 ["javdb", "dmm", "javbus"]
   * @example
   * // Pydantic: Field(json_schema_extra={"x-ordered": True})
   */
  "x-ordered"?: boolean;
  /**
   * 长列表: 用固定高度可滚动容器渲染, 而非自由换行铺开.
   * @example
   * // Pydantic: Field(json_schema_extra={"x-long": True})
   */
  "x-long"?: boolean;
}

/** 对象/字典字段扩展 - 仅用于 type: "object" */
export interface AmaneObjectExtensions extends AmaneBaseExtensions {
  /**
   * 冻结 dict 的 key 集合: 禁止用户增删项, 仅允许编辑已有项的值.
   * key 集合由 propertyNames.enum 定义.
   * @example
   * // Pydantic: Field(json_schema_extra={"x-frozen-keys": True, "propertyNames": {"enum": [...]}})
   */
  "x-frozen-keys"?: boolean;
}

// ==================== Base schema type ====================

type Discriminator = {
  // value -> type ref
  mapping: Record<string, string>;
  // field name
  propertyName: string;
};

/**
 * Base schema - includes all JSON Schema + Amane extension fields as optional.
 * Internal references use JSONSchemaObject (object-only) for ergonomic access,
 * except additionalProperties which allows boolean per JSON Schema spec.
 */
type BaseJSONSchema = {
  // JSON Schema metadata
  $id?: string;
  $comment?: string;
  $schema?: string;
  $defs?: Record<string, JSONSchemaObject>;
  title?: string;
  description?: string;
  deprecated?: boolean;
  readOnly?: boolean;
  writeOnly?: boolean;
  nullable?: boolean;
  default?: unknown;
  /** 把字段值固定为某个常量, 通常用于 discriminated union 的判别字段 */
  const?: unknown;
  discriminator?: Discriminator;
  // Composition
  anyOf?: JSONSchemaObject[];
  oneOf?: JSONSchemaObject[];
  allOf?: JSONSchemaObject[];
  $ref?: string;
  // String constraints
  format?: string;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  // Numeric constraints
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  multipleOf?: number;
  // Array constraints
  items?: JSONSchemaObject;
  minItems?: number;
  maxItems?: number;
  uniqueItems?: boolean;
  // Object constraints
  properties?: Record<string, JSONSchemaObject>;
  propertyNames?: JSONSchemaObject;
  required?: string[];
} & AmaneBaseExtensions;

// ==================== Per-type schemas ====================

export type NullJSONSchema = BaseJSONSchema & {
  type: "null";
  default?: null;
};

export type BooleanJSONSchema = BaseJSONSchema & {
  type: "boolean";
  default?: boolean;
};

/** Numeric field without enum */
export type NumericJSONSchema = BaseJSONSchema & {
  type: "number" | "integer";
  default?: number;
};

/** Numeric field with enum constraint */
export type NumericEnumJSONSchema = BaseJSONSchema & {
  type: "number" | "integer";
  enum: number[];
  default?: number;
} & AmaneEnumExtensions;

/** Text (string) field - no enum, no PathPicker widget */
export type TextJSONSchema = BaseJSONSchema & {
  type: "string";
  "x-widget"?: Exclude<AmaneWidget, "PathPicker">;
  default?: string;
} & AmaneTextExtensions;

/** Text field with enum constraint */
export type TextEnumJSONSchema = BaseJSONSchema & {
  type: "string";
  enum: string[];
  default?: string;
} & AmaneEnumExtensions;

/** Path picker field - string with x-widget: "PathPicker" */
export type PathJSONSchema = BaseJSONSchema & {
  type: "string";
  default?: string;
} & AmanePathExtensions;

/** Library picker field - integer with x-widget: "LibraryPicker" */
export type LibraryJSONSchema = BaseJSONSchema & {
  type: "integer";
  "x-widget": "LibraryPicker";
  default?: number;
};

/** Array field */
export type ArrayJSONSchema = BaseJSONSchema & {
  type: "array";
  items?: JSONSchemaObject;
  default?: unknown[];
} & AmaneArrayExtensions;

/** Object field with known properties */
export type ObjectJSONSchema = BaseJSONSchema & {
  type: "object";
  properties?: Record<string, JSONSchemaObject>;
  default?: Record<string, unknown>;
};

/** Dict/map field - object with required additionalProperties (schema object) */
export type DictJSONSchema = BaseJSONSchema & {
  type: "object";
  additionalProperties: JSONSchemaObject;
  properties?: Record<string, JSONSchemaObject>;
  default?: Record<string, unknown>;
} & AmaneObjectExtensions;

/** Composed schema - anyOf/oneOf/allOf/$ref, type field is optional */
export type ComposedJSONSchema = BaseJSONSchema & {
  type?: string;
};

// ==================== Main union types ====================

/**
 * Object-only schema type - excludes boolean shorthand.
 * Used in component props and most internal positions where schemas
 * are always resolved objects.
 */
export type JSONSchemaObject =
  | NullJSONSchema
  | BooleanJSONSchema
  | NumericJSONSchema
  | NumericEnumJSONSchema
  | TextJSONSchema
  | TextEnumJSONSchema
  | PathJSONSchema
  | LibraryJSONSchema
  | ArrayJSONSchema
  | ObjectJSONSchema
  | DictJSONSchema
  | ComposedJSONSchema;

/**
 * Full Amane JSON Schema type - includes boolean shorthand per JSON Schema spec.
 * Boolean schemas (`true` = accept all, `false` = reject all) are valid in positions
 * like additionalProperties. Components use JSONSchemaObject instead.
 */
export type JSONSchema = boolean | JSONSchemaObject;

export type EnumSchema = TextEnumJSONSchema | NumericEnumJSONSchema;

// ==================== Form instance type ====================

/** Typed wrapper for TanStack Form instance used throughout schema-form fields. */
export interface SchemaFormInstance {
  Field: React.ComponentType<{
    name: string;
    children: (field: import("@tanstack/react-form").AnyFieldApi) => React.ReactNode;
  }>;
}

// ==================== Field props ====================

/**
 * Visual rendering mode for a field.
 *
 * - `default` - full chrome: label + description + outer container (used in
 *   settings pages, the main use case).
 * - `bare` - strip chrome, render only the input control. The caller takes
 *   responsibility for layout/labeling. Used inside collection containers
 *   (DictField KV row, future table cell editor, etc.).
 *
 * Variant only governs chrome. Schema-driven behavior - multiline text,
 * nullable Clear button, enum toggle/select switching - is unaffected by
 * variant. If a real conflict arises, expose a focused prop for that case.
 */
export type FieldVariant = "default" | "bare";

export interface FieldProps<S extends JSONSchemaObject = JSONSchemaObject> {
  name: string;
  schema: S;
  label: string;
  description?: string;
  form: SchemaFormInstance;
  /** i18n lookup path (may differ from form binding `name` in dict contexts). */
  i18nPath: string;
  /** i18n lookup prefix: "namespace:pathPrefix" (e.g., "settings:fields", "tasks"). */
  i18nPrefix: string;
  /** Visual mode (see FieldVariant). Defaults to "default". */
  variant?: FieldVariant;
}

export interface ArrayFieldProps<IS extends JSONSchemaObject> extends FieldProps<ArrayJSONSchema> {
  itemSchema: IS;
}

export interface DictFieldProps<
  VS extends JSONSchemaObject = JSONSchemaObject,
> extends FieldProps<DictJSONSchema> {
  valueSchema: VS;
}
