import { NumberInput } from "@mantine/core";
import type { AnyFieldApi } from "@tanstack/react-form";
import type { FieldProps, NumericJSONSchema } from "../schema";
import { getEffectiveType, isNullable } from "../schema";
import { FieldChrome } from "./field-chrome";
import { fieldError } from "./field-error";

export function NumericField({
  name,
  label,
  description,
  schema,
  form,
  variant,
}: FieldProps<NumericJSONSchema>) {
  const nullable = isNullable(schema);
  const effectiveSchema = getEffectiveType(schema);
  const isInteger = typeof effectiveSchema === "object" && effectiveSchema.type === "integer";

  return (
    <form.Field name={name}>
      {(field: AnyFieldApi) => (
        <FieldChrome
          variant={variant}
          htmlFor={name}
          label={label}
          description={description}
          error={fieldError(field)}
        >
          <NumberInput
            id={name}
            allowDecimal={!isInteger}
            value={field.state.value == null ? "" : (field.state.value as number)}
            onChange={(value) => {
              if (value === "") {
                field.handleChange(nullable ? null : 0);
                return;
              }
              field.handleChange(
                typeof value === "string"
                  ? isInteger
                    ? Number.parseInt(value, 10)
                    : Number.parseFloat(value)
                  : value,
              );
            }}
          />
        </FieldChrome>
      )}
    </form.Field>
  );
}
