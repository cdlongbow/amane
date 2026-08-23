import {
  Accordion,
  ActionIcon,
  Anchor,
  Box,
  Button,
  Group,
  Modal,
  NumberInput,
  Select,
  Stack,
  Text,
  TextInput,
  Textarea,
  TagsInput,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconArrowDown, IconArrowUp, IconTrash } from "@tabler/icons-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { ActorGender, ActorResponse, ActorUpdateRequest } from "@/client/types.gen";
import { FanartLightbox } from "@/components/media/fanart-lightbox";
import { proxyImageUrl } from "@/lib/utils";
import { ProxyImage } from "@/components/media/proxy-image";

export interface ActorEditDialogProps {
  actor: ActorResponse;
  opened: boolean;
  onClose: () => void;
  onSave: (patch: ActorUpdateRequest) => void;
  saving?: boolean;
}

function numOrNull(v: number | string): number | null {
  if (v === "" || v == null) return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** 演员人物字段编辑弹窗 - 含头像调序, 别名 tags, raw 只读来源. */
export function ActorEditDialog({
  actor,
  opened,
  onClose,
  onSave,
  saving = false,
}: ActorEditDialogProps) {
  const { t } = useTranslation(["metadata", "common"]);
  const [gender, setGender] = useState<ActorGender>(actor.gender ?? "unknown");
  const [birthday, setBirthday] = useState(actor.birthday ?? "");
  const [birthplace, setBirthplace] = useState(actor.birthplace ?? "");
  const [height, setHeight] = useState<number | string>(actor.height ?? "");
  const [bust, setBust] = useState<number | string>(actor.bust ?? "");
  const [waist, setWaist] = useState<number | string>(actor.waist ?? "");
  const [hip, setHip] = useState<number | string>(actor.hip ?? "");
  const [cup, setCup] = useState(actor.cup ?? "");
  const [tagline, setTagline] = useState(actor.tagline ?? "");
  const [overview, setOverview] = useState(actor.overview ?? "");
  const [aliases, setAliases] = useState<string[]>(() => [...(actor.aliases ?? [])]);
  const [imageUrls, setImageUrls] = useState<string[]>(() => [...(actor.image_urls ?? [])]);
  const [newImageUrl, setNewImageUrl] = useState("");
  const [lightboxOpen, { open: openLightbox, close: closeLightbox }] = useDisclosure(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  const formKey = opened ? actor.id : "closed";
  const [prevFormKey, setPrevFormKey] = useState(formKey);
  if (formKey !== prevFormKey) {
    setPrevFormKey(formKey);
    setGender(actor.gender ?? "unknown");
    setBirthday(actor.birthday ?? "");
    setBirthplace(actor.birthplace ?? "");
    setHeight(actor.height ?? "");
    setBust(actor.bust ?? "");
    setWaist(actor.waist ?? "");
    setHip(actor.hip ?? "");
    setCup(actor.cup ?? "");
    setTagline(actor.tagline ?? "");
    setOverview(actor.overview ?? "");
    setAliases([...(actor.aliases ?? [])]);
    setImageUrls([...(actor.image_urls ?? [])]);
    setNewImageUrl("");
    closeLightbox();
  }

  const rawSites = Object.entries(actor.raw ?? {});

  function moveImage(index: number, delta: number) {
    const next = index + delta;
    if (next < 0 || next >= imageUrls.length) return;
    setImageUrls((prev) => {
      const copy = [...prev];
      const tmp = copy[index];
      copy[index] = copy[next];
      copy[next] = tmp;
      return copy;
    });
  }

  function handleSave() {
    onSave({
      gender,
      birthday: birthday.trim() || null,
      birthplace: birthplace.trim() || null,
      height: numOrNull(height),
      bust: numOrNull(bust),
      waist: numOrNull(waist),
      hip: numOrNull(hip),
      cup: cup.trim() || null,
      tagline: tagline.trim() || null,
      overview: overview.trim() || null,
      aliases: aliases.map((a) => a.trim()).filter(Boolean),
      image_urls: imageUrls,
    });
  }

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={`${t("actors.editTitle")} — ${actor.name}`}
      size="lg"
    >
      <Stack gap="sm">
        <Select
          label={t("browse.person.gender")}
          description={t("actors.genderHint")}
          value={gender}
          onChange={(v) => {
            if (v === "female" || v === "male" || v === "unknown") setGender(v);
          }}
          data={[
            { value: "female", label: t("browse.person.genderFemale") },
            { value: "male", label: t("browse.person.genderMale") },
            { value: "unknown", label: t("browse.person.genderUnknown") },
          ]}
          allowDeselect={false}
        />
        <TextInput
          label={t("browse.person.birthday")}
          description={t("browse.person.birthdayFormat")}
          value={birthday}
          onChange={(e) => setBirthday(e.currentTarget.value)}
          placeholder="YYYY-MM-DD"
        />
        <TextInput
          label={t("browse.person.birthplace")}
          value={birthplace}
          onChange={(e) => setBirthplace(e.currentTarget.value)}
        />
        <Group grow>
          <NumberInput
            label={t("browse.person.height")}
            value={height}
            onChange={setHeight}
            min={0}
            allowDecimal={false}
          />
          <TextInput
            label={t("browse.person.cup")}
            value={cup}
            onChange={(e) => setCup(e.currentTarget.value)}
          />
        </Group>
        <Group grow>
          <NumberInput label="B" value={bust} onChange={setBust} min={0} allowDecimal={false} />
          <NumberInput label="W" value={waist} onChange={setWaist} min={0} allowDecimal={false} />
          <NumberInput label="H" value={hip} onChange={setHip} min={0} allowDecimal={false} />
        </Group>
        <TextInput
          label={t("browse.person.tagline")}
          value={tagline}
          onChange={(e) => setTagline(e.currentTarget.value)}
        />
        <Textarea
          label={t("browse.person.overview")}
          value={overview}
          onChange={(e) => setOverview(e.currentTarget.value)}
          minRows={3}
          autosize
        />
        <TagsInput
          label={t("browse.person.aliases")}
          description={t("actors.aliasesHint")}
          value={aliases}
          onChange={setAliases}
          splitChars={[",", "，", "\n"]}
          clearable
        />

        <Stack gap="xs">
          <Text size="sm" fw={500}>
            {t("actors.imagesEdit")}
          </Text>
          <Text size="xs" c="dimmed">
            {t("actors.imagesEditHint")}
          </Text>
          {imageUrls.map((url, index) => (
            <Group key={`${url}-${index}`} gap="xs" wrap="nowrap" align="center">
              <Box
                component="button"
                type="button"
                onClick={() => {
                  setLightboxIndex(index);
                  openLightbox();
                }}
                style={{
                  padding: 0,
                  border: "none",
                  background: "none",
                  cursor: "zoom-in",
                  lineHeight: 0,
                  borderRadius: "var(--mantine-radius-sm)",
                  overflow: "hidden",
                  flexShrink: 0,
                }}
              >
                <ProxyImage
                  src={proxyImageUrl(url) ?? url}
                  alt=""
                  referrerPolicy="no-referrer"
                  style={{
                    display: "block",
                    width: 36,
                    height: 48,
                    objectFit: "cover",
                  }}
                  placeholder={
                    <span style={{ display: "block", width: 36, height: 48 }} aria-hidden />
                  }
                />
              </Box>
              <Text size="xs" style={{ flex: 1, minWidth: 0 }} truncate title={url}>
                {index === 0 ? `${t("actors.primaryImage")} · ${url}` : url}
              </Text>
              <ActionIcon
                variant="subtle"
                disabled={index === 0}
                onClick={() => moveImage(index, -1)}
                aria-label="up"
              >
                <IconArrowUp size={14} />
              </ActionIcon>
              <ActionIcon
                variant="subtle"
                disabled={index === imageUrls.length - 1}
                onClick={() => moveImage(index, 1)}
                aria-label="down"
              >
                <IconArrowDown size={14} />
              </ActionIcon>
              <ActionIcon
                variant="subtle"
                color="red"
                onClick={() => setImageUrls((prev) => prev.filter((_, i) => i !== index))}
                aria-label="remove"
              >
                <IconTrash size={14} />
              </ActionIcon>
            </Group>
          ))}
          <Group gap="xs" wrap="nowrap">
            <TextInput
              style={{ flex: 1 }}
              placeholder="https://"
              value={newImageUrl}
              onChange={(e) => setNewImageUrl(e.currentTarget.value)}
            />
            <Button
              variant="light"
              disabled={!/^https?:\/\//i.test(newImageUrl.trim())}
              onClick={() => {
                const url = newImageUrl.trim();
                setImageUrls((prev) => (prev.includes(url) ? prev : [...prev, url]));
                setNewImageUrl("");
              }}
            >
              {t("common:actions.add")}
            </Button>
          </Group>
        </Stack>

        {rawSites.length > 0 && (
          <Stack gap="xs" pt="xs">
            <Text size="sm" fw={500}>
              {t("actors.rawSources")}
            </Text>
            <Text size="xs" c="dimmed">
              {t("actors.rawSourcesHint")}
            </Text>
            <Accordion variant="separated" radius="md">
              {rawSites.map(([site, payload]) => (
                <Accordion.Item key={site} value={site}>
                  <Accordion.Control>{site}</Accordion.Control>
                  <Accordion.Panel>
                    <RawSiteSummary site={site} payload={payload} />
                  </Accordion.Panel>
                </Accordion.Item>
              ))}
            </Accordion>
          </Stack>
        )}

        <Group justify="flex-end" mt="sm">
          <Button variant="default" onClick={onClose}>
            {t("common:actions.cancel")}
          </Button>
          <Button loading={saving} onClick={handleSave}>
            {t("common:actions.save")}
          </Button>
        </Group>
      </Stack>

      {lightboxOpen && imageUrls.length > 0 && (
        <FanartLightbox images={imageUrls} initialIndex={lightboxIndex} onClose={closeLightbox} />
      )}
    </Modal>
  );
}

function RawSiteSummary({ site, payload }: { site: string; payload: unknown }) {
  const { t } = useTranslation("metadata");
  if (!payload || typeof payload !== "object") {
    return (
      <Text size="xs" c="dimmed">
        —
      </Text>
    );
  }
  const data = payload as Record<string, unknown>;
  const rows: { label: string; value: string }[] = [];
  const push = (label: string, value: unknown) => {
    if (value == null || value === "") return;
    if (typeof value === "string" || typeof value === "number") {
      rows.push({ label, value: String(value) });
    }
  };
  push(t("browse.person.birthday"), data.birthday);
  push(t("browse.person.birthplace"), data.birthplace);
  push(t("browse.person.height"), data.height);
  push(t("browse.person.cup"), data.cup);
  push(t("browse.person.tagline"), data.tagline);
  push(t("browse.person.overview"), data.overview);
  push(t("browse.person.sourceUrl"), data.source_url);
  if (Array.isArray(data.aliases) && data.aliases.length > 0) {
    rows.push({
      label: t("browse.person.aliases"),
      value: data.aliases.filter((a): a is string => typeof a === "string").join(" · "),
    });
  }
  if (Array.isArray(data.image_urls) && data.image_urls.length > 0) {
    rows.push({
      label: t("browse.person.images"),
      value: String(data.image_urls.length),
    });
  }

  if (rows.length === 0) {
    return (
      <Text size="xs" c="dimmed" ff="monospace" style={{ whiteSpace: "pre-wrap" }}>
        {JSON.stringify(data, null, 2)}
      </Text>
    );
  }

  return (
    <Stack gap={6}>
      {rows.map((row) => (
        <Group key={`${site}-${row.label}`} gap="xs" align="flex-start" wrap="nowrap">
          <Text size="xs" c="dimmed" w={72} style={{ flexShrink: 0 }}>
            {row.label}
          </Text>
          {row.label === t("browse.person.sourceUrl") && /^https?:\/\//i.test(row.value) ? (
            <Anchor href={row.value} target="_blank" rel="noreferrer" size="xs" lineClamp={2}>
              {row.value}
            </Anchor>
          ) : (
            <Text size="xs" style={{ whiteSpace: "pre-wrap" }}>
              {row.value}
            </Text>
          )}
        </Group>
      ))}
    </Stack>
  );
}
