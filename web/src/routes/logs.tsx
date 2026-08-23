import {
  Badge,
  Button,
  Group,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { IconAlertCircle, IconInfoCircle, IconSearch, IconTrash } from "@tabler/icons-react";
import { createFileRoute } from "@tanstack/react-router";
import type { ParseKeys } from "i18next";
import { filter, LiqeError, parse } from "liqe";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Virtuoso } from "react-virtuoso";
import { exhaustiveRecord } from "@/lib/exhaustive";
import {
  LOG_LEVELS,
  type LogEntry,
  type LogLevel,
  logLevelMantineColor,
  useLogStore,
} from "@/stores/logs";
import { useUIStore } from "@/stores/ui";

export const Route = createFileRoute("/logs")({ component: LogsPage });

const LEVEL_I18N_KEY = exhaustiveRecord<LogLevel>()({
  DEBUG: "logs:levels.debug",
  INFO: "logs:levels.info",
  WARNING: "logs:levels.warn",
  ERROR: "logs:levels.error",
  CRITICAL: "logs:levels.critical",
} as const satisfies Record<LogLevel, ParseKeys<["logs", "common"]>>);

function matchesText(entry: LogEntry, query: string): boolean {
  try {
    const ast = parse(query);
    return filter(ast, [entry]).length > 0;
  } catch (err) {
    if (err instanceof LiqeError) {
      const needle = query.toLowerCase();
      return (
        entry.message.toLowerCase().includes(needle) || entry.source.toLowerCase().includes(needle)
      );
    }
    throw err;
  }
}

function renderLogRow(_index: number, entry: LogEntry) {
  return <LogRow entry={entry} />;
}

function LogRow({ entry }: { entry: LogEntry }) {
  const extra = Object.entries(entry).filter(
    ([k]) => !["id", "timestamp", "level", "source", "message"].includes(k),
  );
  return (
    <Group
      gap="sm"
      wrap="nowrap"
      px="sm"
      py={6}
      align="flex-start"
      style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}
    >
      <Text size="xs" c="dimmed" ff="monospace" style={{ whiteSpace: "nowrap", flexShrink: 0 }}>
        {new Date(entry.timestamp).toLocaleTimeString()}
      </Text>
      <Badge
        size="xs"
        color={logLevelMantineColor(entry.level)}
        variant="light"
        style={{ flexShrink: 0 }}
      >
        {entry.level}
      </Badge>
      <Text
        size="xs"
        c="dimmed"
        ff="monospace"
        style={{ flexShrink: 0, minWidth: 90 }}
        lineClamp={1}
      >
        {entry.source}
      </Text>
      <Text size="sm" style={{ flex: 1, wordBreak: "break-word" }}>
        {entry.message}
        {extra.length > 0 && (
          <Text component="span" size="xs" c="dimmed" ml={6}>
            {extra
              .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
              .join(" ")}
          </Text>
        )}
      </Text>
    </Group>
  );
}

function LogsPage() {
  const { t } = useTranslation(["logs", "common"]);
  const entries = useLogStore((s) => s.entries);
  const clear = useLogStore((s) => s.clear);
  const autoScroll = useUIStore((s) => s.autoScroll);
  const setAutoScroll = useUIStore((s) => s.setAutoScroll);
  const levelFilter = useUIStore((s) => s.logLevelFilter);
  const setLevelFilter = useUIStore((s) => s.setLogLevelFilter);

  const [query, setQuery] = useState("");

  function toggleLevel(level: LogLevel) {
    setLevelFilter(
      levelFilter.includes(level)
        ? levelFilter.filter((l) => l !== level)
        : [...levelFilter, level],
    );
  }

  const { items: filtered, error: queryError } = useMemo(() => {
    const byLevel =
      levelFilter.length === 0 ? entries : entries.filter((e) => levelFilter.includes(e.level));
    const q = query.trim();
    if (!q) return { items: byLevel, error: null };
    try {
      parse(q);
    } catch (err) {
      return {
        items: byLevel,
        error: err instanceof LiqeError ? err.message : t("common:status.error"),
      };
    }
    return { items: byLevel.filter((e) => matchesText(e, q)), error: null };
  }, [entries, levelFilter, query, t]);

  return (
    <Stack gap="md" h="calc(100vh - 100px)">
      <Group justify="space-between" wrap="wrap">
        <Title order={2}>{t("title")}</Title>
        <Group gap="xs">
          <Switch
            label={t("actions.autoScroll")}
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.currentTarget.checked)}
          />
          <Button
            size="xs"
            variant="light"
            color="red"
            leftSection={<IconTrash size={14} />}
            onClick={clear}
          >
            {t("actions.clear")}
          </Button>
        </Group>
      </Group>

      <Group gap="xs">
        <TextInput
          flex={1}
          leftSection={<IconSearch size={16} />}
          placeholder={t("searchPlaceholder")}
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          error={queryError}
          rightSection={
            <Tooltip label={t("queryHelp.fallback")} multiline w={240}>
              <IconInfoCircle size={16} style={{ opacity: 0.6 }} />
            </Tooltip>
          }
        />
      </Group>

      <Group gap="xs">
        {LOG_LEVELS.map((level) => (
          <Button
            key={level}
            size="xs"
            variant={levelFilter.includes(level) ? "filled" : "light"}
            color={logLevelMantineColor(level)}
            onClick={() => toggleLevel(level)}
          >
            {t(LEVEL_I18N_KEY[level])}
          </Button>
        ))}
      </Group>

      <div
        style={{
          flex: 1,
          minHeight: 300,
          border: "1px solid var(--mantine-color-default-border)",
          borderRadius: "var(--mantine-radius-md)",
        }}
      >
        {filtered.length === 0 ? (
          <Group justify="center" py="xl">
            <IconAlertCircle size={16} style={{ opacity: 0.5 }} />
            <Text c="dimmed" size="sm">
              {entries.length === 0 ? t("empty") : t("noMatch")}
            </Text>
          </Group>
        ) : (
          <Virtuoso
            style={{ height: "100%" }}
            data={filtered}
            followOutput={autoScroll ? "smooth" : false}
            itemContent={renderLogRow}
          />
        )}
      </div>
    </Stack>
  );
}
