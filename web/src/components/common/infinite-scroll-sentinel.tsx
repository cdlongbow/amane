import { Center, Loader, Text } from "@mantine/core";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useLatestRef } from "@/hooks/use-latest-ref";

interface InfiniteScrollSentinelProps {
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => unknown;
  /** 已加载条数 / 总条数文案; 无更多页时也展示. */
  loadedLabel?: string;
}

export function InfiniteScrollSentinel({
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
  loadedLabel,
}: InfiniteScrollSentinelProps) {
  const { t } = useTranslation("common");
  const ref = useRef<HTMLDivElement>(null);
  const fetchingRef = useLatestRef(isFetchingNextPage);
  const fetchRef = useLatestRef(fetchNextPage);

  useEffect(() => {
    const el = ref.current;
    if (!el || !hasNextPage) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting) && !fetchingRef.current) {
          fetchRef.current();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [fetchRef, fetchingRef, hasNextPage]);

  return (
    <Center ref={ref} py="md">
      {isFetchingNextPage ? (
        <Loader size="sm" />
      ) : loadedLabel ? (
        <Text size="sm" c="dimmed">
          {loadedLabel}
        </Text>
      ) : hasNextPage ? (
        <Text size="sm" c="dimmed">
          {t("pagination.next")}
        </Text>
      ) : null}
    </Center>
  );
}
