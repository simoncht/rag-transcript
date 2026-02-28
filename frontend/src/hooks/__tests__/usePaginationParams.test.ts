import { renderHook, act } from "@testing-library/react";

const mockReplace = jest.fn();
let mockSearchParams = new URLSearchParams();

jest.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => "/videos",
}));

import { usePaginationParams } from "../usePaginationParams";

beforeEach(() => {
  mockSearchParams = new URLSearchParams();
  mockReplace.mockClear();
});

describe("usePaginationParams", () => {
  it("returns correct defaults when URL has no params", () => {
    const { result } = renderHook(() => usePaginationParams());
    expect(result.current.page).toBe(1);
    expect(result.current.pageSize).toBe(20);
    expect(result.current.status).toBeUndefined();
    expect(result.current.skip).toBe(0);
  });

  it("reads page from URL search params", () => {
    mockSearchParams = new URLSearchParams("page=3");
    const { result } = renderHook(() => usePaginationParams());
    expect(result.current.page).toBe(3);
    expect(result.current.skip).toBe(40); // (3-1) * 20
  });

  it("reads pageSize from URL search params", () => {
    mockSearchParams = new URLSearchParams("pageSize=50");
    const { result } = renderHook(() => usePaginationParams());
    expect(result.current.pageSize).toBe(50);
  });

  it("reads status from URL search params", () => {
    mockSearchParams = new URLSearchParams("status=completed");
    const { result } = renderHook(() => usePaginationParams());
    expect(result.current.status).toBe("completed");
  });

  it("defaults invalid page to 1", () => {
    mockSearchParams = new URLSearchParams("page=-1");
    const { result } = renderHook(() => usePaginationParams());
    expect(result.current.page).toBe(1);
  });

  it("defaults non-numeric page to 1", () => {
    mockSearchParams = new URLSearchParams("page=abc");
    const { result } = renderHook(() => usePaginationParams());
    expect(result.current.page).toBe(1);
  });

  it("defaults invalid pageSize to 20", () => {
    mockSearchParams = new URLSearchParams("pageSize=25");
    const { result } = renderHook(() => usePaginationParams());
    expect(result.current.pageSize).toBe(20);
  });

  it("setPage updates URL with page param", () => {
    const { result } = renderHook(() => usePaginationParams());
    act(() => result.current.setPage(3));
    expect(mockReplace).toHaveBeenCalledWith("/videos?page=3", { scroll: false });
  });

  it("setPage(1) removes page param from URL", () => {
    mockSearchParams = new URLSearchParams("page=3");
    const { result } = renderHook(() => usePaginationParams());
    act(() => result.current.setPage(1));
    expect(mockReplace).toHaveBeenCalledWith("/videos", { scroll: false });
  });

  it("setPageSize resets page to 1", () => {
    mockSearchParams = new URLSearchParams("page=3");
    const { result } = renderHook(() => usePaginationParams());
    act(() => result.current.setPageSize(50));
    expect(mockReplace).toHaveBeenCalledWith("/videos?pageSize=50", { scroll: false });
  });

  it("setPageSize(20) removes pageSize param (default)", () => {
    mockSearchParams = new URLSearchParams("pageSize=50");
    const { result } = renderHook(() => usePaginationParams());
    act(() => result.current.setPageSize(20));
    expect(mockReplace).toHaveBeenCalledWith("/videos", { scroll: false });
  });

  it("setStatus resets page to 1", () => {
    mockSearchParams = new URLSearchParams("page=3");
    const { result } = renderHook(() => usePaginationParams());
    act(() => result.current.setStatus("completed"));
    expect(mockReplace).toHaveBeenCalledWith("/videos?status=completed", { scroll: false });
  });

  it("setStatus(undefined) removes status param", () => {
    mockSearchParams = new URLSearchParams("status=completed");
    const { result } = renderHook(() => usePaginationParams());
    act(() => result.current.setStatus(undefined));
    expect(mockReplace).toHaveBeenCalledWith("/videos", { scroll: false });
  });

  it("computes correct skip for page 2 with pageSize 10", () => {
    mockSearchParams = new URLSearchParams("page=2&pageSize=10");
    const { result } = renderHook(() => usePaginationParams());
    expect(result.current.skip).toBe(10);
  });
});
