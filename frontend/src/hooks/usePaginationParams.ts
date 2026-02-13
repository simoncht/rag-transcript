"use client";

import { useCallback, useMemo } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";

const ALLOWED_PAGE_SIZES = [10, 20, 50] as const;
const DEFAULT_PAGE_SIZE = 20;

export type PageSize = (typeof ALLOWED_PAGE_SIZES)[number];

export function usePaginationParams() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const page = useMemo(() => {
    const raw = Number(searchParams.get("page"));
    return Number.isInteger(raw) && raw >= 1 ? raw : 1;
  }, [searchParams]);

  const pageSize = useMemo(() => {
    const raw = Number(searchParams.get("pageSize"));
    return ALLOWED_PAGE_SIZES.includes(raw as PageSize)
      ? (raw as PageSize)
      : DEFAULT_PAGE_SIZE;
  }, [searchParams]);

  const status = useMemo(() => {
    return searchParams.get("status") || undefined;
  }, [searchParams]);

  const q = useMemo(() => {
    return searchParams.get("q") || undefined;
  }, [searchParams]);

  const sort = useMemo(() => {
    return searchParams.get("sort") || undefined;
  }, [searchParams]);

  const channel = useMemo(() => {
    return searchParams.get("channel") || undefined;
  }, [searchParams]);

  const tags = useMemo(() => {
    return searchParams.get("tags") || undefined;
  }, [searchParams]);

  const durationMin = useMemo(() => {
    const raw = searchParams.get("duration_min");
    return raw ? Number(raw) : undefined;
  }, [searchParams]);

  const durationMax = useMemo(() => {
    const raw = searchParams.get("duration_max");
    return raw ? Number(raw) : undefined;
  }, [searchParams]);

  const skip = (page - 1) * pageSize;

  const updateParams = useCallback(
    (updates: Record<string, string | undefined>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === undefined || value === "") {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      }
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [searchParams, router, pathname]
  );

  const setPage = useCallback(
    (newPage: number) => {
      updateParams({ page: newPage === 1 ? undefined : String(newPage) });
    },
    [updateParams]
  );

  const setPageSize = useCallback(
    (newSize: PageSize) => {
      updateParams({
        pageSize: newSize === DEFAULT_PAGE_SIZE ? undefined : String(newSize),
        page: undefined, // reset to page 1
      });
    },
    [updateParams]
  );

  const setStatus = useCallback(
    (newStatus: string | undefined) => {
      updateParams({
        status: newStatus,
        page: undefined, // reset to page 1
      });
    },
    [updateParams]
  );

  const setQ = useCallback(
    (newQ: string | undefined) => {
      updateParams({
        q: newQ,
        page: undefined,
      });
    },
    [updateParams]
  );

  const setSort = useCallback(
    (newSort: string | undefined) => {
      updateParams({ sort: newSort });
    },
    [updateParams]
  );

  const setChannel = useCallback(
    (newChannel: string | undefined) => {
      updateParams({
        channel: newChannel,
        page: undefined,
      });
    },
    [updateParams]
  );

  const setTags = useCallback(
    (newTags: string | undefined) => {
      updateParams({
        tags: newTags,
        page: undefined,
      });
    },
    [updateParams]
  );

  const setDuration = useCallback(
    (min: number | undefined, max: number | undefined) => {
      updateParams({
        duration_min: min !== undefined ? String(min) : undefined,
        duration_max: max !== undefined ? String(max) : undefined,
        page: undefined,
      });
    },
    [updateParams]
  );

  const clearAllFilters = useCallback(() => {
    updateParams({
      q: undefined,
      status: undefined,
      sort: undefined,
      channel: undefined,
      tags: undefined,
      duration_min: undefined,
      duration_max: undefined,
      page: undefined,
    });
  }, [updateParams]);

  const hasActiveFilters = !!(q || status || channel || tags || durationMin !== undefined || durationMax !== undefined);

  return {
    page,
    pageSize,
    status,
    q,
    sort,
    channel,
    tags,
    durationMin,
    durationMax,
    skip,
    hasActiveFilters,
    setPage,
    setPageSize,
    setStatus,
    setQ,
    setSort,
    setChannel,
    setTags,
    setDuration,
    clearAllFilters,
  };
}
