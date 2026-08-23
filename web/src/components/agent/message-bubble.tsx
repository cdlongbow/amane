import { Box, Group, Stack, Text } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { MarkdownContent } from "@/components/agent/markdown-content";
import { SavedQueryActions } from "@/components/agent/saved-query-actions";
import type {
  ApprovalAction,
  ToolApproval,
  ToolCallView,
} from "@/components/agent/tool-call-badge";
import { ToolCallGroup } from "@/components/agent/tool-call-badge";
import { TokenUsageBar } from "@/components/agent/token-usage-bar";

export type TurnTokenUsage = {
  input: number;
  cache_read: number;
  cache_write: number;
  output: number;
  requests: number;
};

/** 助手回合内按时间序排列的块: 文本与工具交错. */
export type AssistantBlock =
  | { kind: "text"; id: string; text: string }
  | { kind: "tool"; tool: ToolCallView };

export type ChatMessage =
  | { role: "user"; text: string }
  | {
      role: "assistant";
      blocks: AssistantBlock[];
      savedQueryIds?: number[];
      streaming?: boolean;
      usage?: TurnTokenUsage;
    };

let blockSeq = 0;
export function nextBlockId(prefix: string): string {
  blockSeq += 1;
  return `${prefix}-${blockSeq}`;
}

type RenderChunk =
  | { kind: "text"; id: string; text: string; showCursor: boolean }
  | { kind: "tools"; tools: ToolCallView[] };

function chunkBlocks(blocks: AssistantBlock[], streaming: boolean | undefined): RenderChunk[] {
  const lastTextIdx = blocks.findLastIndex((b) => b.kind === "text");
  const chunks: RenderChunk[] = [];
  let toolBuf: ToolCallView[] = [];

  const flushTools = () => {
    if (toolBuf.length === 0) return;
    chunks.push({ kind: "tools", tools: toolBuf });
    toolBuf = [];
  };

  blocks.forEach((block, idx) => {
    if (block.kind === "tool") {
      toolBuf.push(block.tool);
      return;
    }
    flushTools();
    const showCursor = Boolean(streaming) && idx === lastTextIdx;
    if (!block.text && !showCursor) return;
    chunks.push({ kind: "text", id: block.id, text: block.text, showCursor });
  });
  flushTools();
  return chunks;
}

export function MessageBubble({
  message,
  onPersist,
  onDownload,
  approvalBusy,
  onApprovalAction,
}: {
  message: ChatMessage;
  onPersist?: (id: number) => void;
  onDownload?: (id: number) => void;
  approvalBusy?: boolean;
  onApprovalAction?: (approval: ToolApproval, action: ApprovalAction) => void;
}) {
  const { t } = useTranslation("agent");

  if (message.role === "user") {
    return (
      <Group justify="flex-end" align="flex-start" wrap="nowrap">
        <Stack gap={6} maw="min(640px, 85%)" style={{ alignItems: "flex-end" }}>
          <Text size="xs" c="dimmed">
            {t("you")}
          </Text>
          <Box
            px="md"
            py="sm"
            style={{
              borderRadius: "var(--mantine-radius-md)",
              background: "var(--mantine-color-default-hover)",
              wordBreak: "break-word",
            }}
          >
            <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
              {message.text}
            </Text>
          </Box>
        </Stack>
      </Group>
    );
  }

  const hasContent = message.blocks.length > 0 || Boolean(message.streaming);
  const chunks = chunkBlocks(message.blocks, message.streaming);

  return (
    <Stack gap="sm" w="100%">
      {hasContent && (
        <Text size="xs" c="dimmed">
          {t("assistant")}
        </Text>
      )}
      {chunks.map((chunk, i) => {
        if (chunk.kind === "tools") {
          return (
            <ToolCallGroup
              key={`tools-${i}-${chunk.tools[0]?.toolCallId}`}
              calls={chunk.tools}
              busy={approvalBusy}
              onApprovalAction={onApprovalAction}
            />
          );
        }
        return (
          <Box key={chunk.id} style={{ wordBreak: "break-word" }}>
            <MarkdownContent text={chunk.text} streaming={chunk.showCursor} />
          </Box>
        );
      })}
      {message.streaming && message.blocks.every((b) => b.kind !== "text") && (
        <Text span c="dimmed" size="sm">
          ▍
        </Text>
      )}
      {message.savedQueryIds && message.savedQueryIds.length > 0 && onPersist && onDownload && (
        <SavedQueryActions
          ids={message.savedQueryIds}
          onDownload={onDownload}
          onPersist={onPersist}
        />
      )}
      {message.usage && !message.streaming && <TokenUsageBar usage={message.usage} />}
    </Stack>
  );
}
