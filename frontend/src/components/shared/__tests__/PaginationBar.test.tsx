import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PaginationBar } from "../PaginationBar";

// Mock lucide-react icons to simple spans
jest.mock("lucide-react", () => ({
  ChevronLeft: () => <span data-testid="chevron-left" />,
  ChevronRight: () => <span data-testid="chevron-right" />,
  ChevronsLeft: () => <span data-testid="chevrons-left" />,
  ChevronsRight: () => <span data-testid="chevrons-right" />,
}));

const defaultProps = {
  page: 1,
  pageSize: 20,
  total: 87,
  onPageChange: jest.fn(),
  onPageSizeChange: jest.fn(),
};

beforeEach(() => {
  defaultProps.onPageChange.mockClear();
  defaultProps.onPageSizeChange.mockClear();
});

describe("PaginationBar", () => {
  describe("summary text", () => {
    it("shows correct range for first page", () => {
      render(<PaginationBar {...defaultProps} />);
      const summary = screen.getByText(/Showing/);
      expect(summary).toHaveTextContent("Showing 1 - 20 of 87 items");
    });

    it("shows correct range for middle page", () => {
      render(<PaginationBar {...defaultProps} page={3} />);
      const summary = screen.getByText(/Showing/);
      expect(summary).toHaveTextContent("Showing 41 - 60 of 87 items");
    });

    it("shows correct range for last page with partial results", () => {
      render(<PaginationBar {...defaultProps} page={5} />);
      const summary = screen.getByText(/Showing/);
      expect(summary).toHaveTextContent("Showing 81 - 87 of 87 items");
    });

    it("shows 'No items' when total is 0", () => {
      render(<PaginationBar {...defaultProps} total={0} />);
      expect(screen.getByText("No items")).toBeInTheDocument();
    });

    it("uses custom itemLabel", () => {
      render(<PaginationBar {...defaultProps} itemLabel="videos" />);
      const summary = screen.getByText(/Showing/);
      expect(summary).toHaveTextContent("Showing 1 - 20 of 87 videos");
    });
  });

  describe("page size toggle", () => {
    it("renders all page size options", () => {
      render(<PaginationBar {...defaultProps} />);
      expect(screen.getByLabelText("Show 10 per page")).toBeInTheDocument();
      expect(screen.getByLabelText("Show 20 per page")).toBeInTheDocument();
      expect(screen.getByLabelText("Show 50 per page")).toBeInTheDocument();
    });

    it("marks current page size as pressed", () => {
      render(<PaginationBar {...defaultProps} pageSize={20} />);
      expect(screen.getByLabelText("Show 20 per page")).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByLabelText("Show 10 per page")).toHaveAttribute("aria-pressed", "false");
    });

    it("calls onPageSizeChange when clicking a size", async () => {
      const user = userEvent.setup();
      render(<PaginationBar {...defaultProps} />);
      await user.click(screen.getByLabelText("Show 50 per page"));
      expect(defaultProps.onPageSizeChange).toHaveBeenCalledWith(50);
    });
  });

  describe("page navigation", () => {
    it("hides first/prev buttons on page 1", () => {
      render(<PaginationBar {...defaultProps} page={1} />);
      expect(screen.queryByLabelText("First page")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Previous page")).not.toBeInTheDocument();
    });

    it("shows first/prev buttons on page > 1", () => {
      render(<PaginationBar {...defaultProps} page={2} />);
      expect(screen.getByLabelText("First page")).toBeInTheDocument();
      expect(screen.getByLabelText("Previous page")).toBeInTheDocument();
    });

    it("hides next/last buttons on last page", () => {
      render(<PaginationBar {...defaultProps} page={5} total={87} />);
      expect(screen.queryByLabelText("Next page")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Last page")).not.toBeInTheDocument();
    });

    it("shows next/last buttons when not on last page", () => {
      render(<PaginationBar {...defaultProps} page={1} />);
      expect(screen.getByLabelText("Next page")).toBeInTheDocument();
      expect(screen.getByLabelText("Last page")).toBeInTheDocument();
    });

    it("calls onPageChange with correct page on next click", async () => {
      const user = userEvent.setup();
      render(<PaginationBar {...defaultProps} page={2} />);
      await user.click(screen.getByLabelText("Next page"));
      expect(defaultProps.onPageChange).toHaveBeenCalledWith(3);
    });

    it("calls onPageChange with correct page on prev click", async () => {
      const user = userEvent.setup();
      render(<PaginationBar {...defaultProps} page={3} />);
      await user.click(screen.getByLabelText("Previous page"));
      expect(defaultProps.onPageChange).toHaveBeenCalledWith(2);
    });

    it("calls onPageChange(1) on first page click", async () => {
      const user = userEvent.setup();
      render(<PaginationBar {...defaultProps} page={3} />);
      await user.click(screen.getByLabelText("First page"));
      expect(defaultProps.onPageChange).toHaveBeenCalledWith(1);
    });

    it("calls onPageChange(totalPages) on last page click", async () => {
      const user = userEvent.setup();
      render(<PaginationBar {...defaultProps} page={1} />);
      await user.click(screen.getByLabelText("Last page"));
      expect(defaultProps.onPageChange).toHaveBeenCalledWith(5);
    });

    it("calls onPageChange when clicking a page number", async () => {
      const user = userEvent.setup();
      render(<PaginationBar {...defaultProps} page={1} />);
      await user.click(screen.getByLabelText("Page 3"));
      expect(defaultProps.onPageChange).toHaveBeenCalledWith(3);
    });

    it("marks current page with aria-current", () => {
      render(<PaginationBar {...defaultProps} page={2} />);
      expect(screen.getByLabelText("Page 2")).toHaveAttribute("aria-current", "page");
      expect(screen.getByLabelText("Page 1")).not.toHaveAttribute("aria-current");
    });
  });

  describe("single page", () => {
    it("hides navigation when only one page", () => {
      render(<PaginationBar {...defaultProps} total={15} pageSize={20} />);
      expect(screen.queryByLabelText("Next page")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Previous page")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Page 1")).not.toBeInTheDocument();
    });
  });

  describe("ellipsis logic", () => {
    it("shows all pages when totalPages <= 7", () => {
      // total=100, pageSize=20 → 5 pages
      render(<PaginationBar {...defaultProps} total={100} pageSize={20} page={1} />);
      for (let i = 1; i <= 5; i++) {
        expect(screen.getByLabelText(`Page ${i}`)).toBeInTheDocument();
      }
    });

    it("shows ellipsis for many pages when at start", () => {
      // total=240, pageSize=20 → 12 pages, current=1
      render(<PaginationBar {...defaultProps} total={240} pageSize={20} page={1} />);
      expect(screen.getByLabelText("Page 1")).toBeInTheDocument();
      expect(screen.getByLabelText("Page 5")).toBeInTheDocument();
      expect(screen.getByLabelText("Page 12")).toBeInTheDocument();
      // Should not show pages 6-11
      expect(screen.queryByLabelText("Page 6")).not.toBeInTheDocument();
    });

    it("shows ellipsis on both sides when in middle", () => {
      // total=240, pageSize=20 → 12 pages, current=6
      render(<PaginationBar {...defaultProps} total={240} pageSize={20} page={6} />);
      expect(screen.getByLabelText("Page 1")).toBeInTheDocument();
      expect(screen.getByLabelText("Page 5")).toBeInTheDocument();
      expect(screen.getByLabelText("Page 6")).toBeInTheDocument();
      expect(screen.getByLabelText("Page 7")).toBeInTheDocument();
      expect(screen.getByLabelText("Page 12")).toBeInTheDocument();
      // Pages 2-4 and 8-11 should not be shown
      expect(screen.queryByLabelText("Page 3")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Page 9")).not.toBeInTheDocument();
    });

    it("shows ellipsis only at start when near end", () => {
      // total=240, pageSize=20 → 12 pages, current=12
      render(<PaginationBar {...defaultProps} total={240} pageSize={20} page={12} />);
      expect(screen.getByLabelText("Page 1")).toBeInTheDocument();
      expect(screen.getByLabelText("Page 8")).toBeInTheDocument();
      expect(screen.getByLabelText("Page 12")).toBeInTheDocument();
      // Should not show pages 2-7
      expect(screen.queryByLabelText("Page 3")).not.toBeInTheDocument();
    });
  });
});
