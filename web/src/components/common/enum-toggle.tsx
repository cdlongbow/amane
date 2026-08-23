import { Button, SegmentedControl } from "@mantine/core";

type EnumToggleBase<T extends string | number> = {
  options: readonly T[];
  getLabel: (opt: T, index: number) => string;
  disabled?: boolean;
  /** Stretch to the parent row; default hugs label width. */
  fullWidth?: boolean;
};

type EnumToggleSingle<T extends string | number> = EnumToggleBase<T> & {
  multiple?: false;
  value: T | null | undefined;
  onChange: (next: T) => void;
};

type EnumToggleMultiple<T extends string | number> = EnumToggleBase<T> & {
  multiple: true;
  value: readonly T[] | null | undefined;
  onChange: (next: T[]) => void;
};

/** Segmented enum: sliding indicator, item separators; `fullWidth` fills the row. */
export function EnumToggle<T extends string | number>(
  props: EnumToggleSingle<T> | EnumToggleMultiple<T>,
) {
  const { options, getLabel, multiple, disabled, fullWidth = false } = props;

  if (multiple) {
    return (
      <Button.Group
        style={{
          width: fullWidth ? "100%" : "max-content",
          maxWidth: "100%",
        }}
      >
        {options.map((opt, i) => {
          const selected = (props.value ?? []).includes(opt);
          return (
            <Button
              key={String(opt)}
              type="button"
              size="compact-sm"
              variant={selected ? "filled" : "default"}
              disabled={disabled}
              style={fullWidth ? { flex: 1 } : undefined}
              onClick={() => {
                const arr = [...(props.value ?? [])];
                const idx = arr.indexOf(opt);
                if (idx >= 0) arr.splice(idx, 1);
                else arr.push(opt);
                props.onChange(arr);
              }}
            >
              {getLabel(opt, i)}
            </Button>
          );
        })}
      </Button.Group>
    );
  }

  return (
    <SegmentedControl
      size="sm"
      radius="sm"
      withItemsBorders
      fullWidth={fullWidth}
      disabled={disabled}
      w={fullWidth ? undefined : "max-content"}
      maw="100%"
      styles={{
        control: fullWidth ? undefined : { flex: "0 0 auto" },
      }}
      value={props.value == null ? "" : String(props.value)}
      onChange={(v) => {
        const next = options.find((opt) => String(opt) === v);
        if (next === undefined || props.value === next) return;
        props.onChange(next);
      }}
      data={options.map((opt, i) => ({
        value: String(opt),
        label: getLabel(opt, i),
      }))}
    />
  );
}
