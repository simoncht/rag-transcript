"use client";

import { useState, useRef, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { conversationsApi } from "@/lib/api/conversations";
import { Input } from "@/components/ui/input";

interface InlineRenameInputProps {
  conversationId: string;
  currentTitle: string;
  onComplete: () => void;
  className?: string;
}

export function InlineRenameInput({
  conversationId,
  currentTitle,
  onComplete,
  className,
}: InlineRenameInputProps) {
  const [value, setValue] = useState(currentTitle);
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const savedRef = useRef(false);

  const renameMutation = useMutation({
    mutationFn: (title: string) =>
      conversationsApi.update(conversationId, title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({
        queryKey: ["conversation", conversationId],
      });
      onComplete();
    },
    onError: () => {
      onComplete();
    },
  });

  useEffect(() => {
    // Auto-focus and select all text
    const input = inputRef.current;
    if (input) {
      input.focus();
      input.select();
    }
  }, []);

  const save = () => {
    if (savedRef.current) return;
    const trimmed = value.trim();
    if (!trimmed || trimmed === currentTitle) {
      onComplete();
      return;
    }
    savedRef.current = true;
    renameMutation.mutate(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    e.stopPropagation();
    if (e.key === "Enter") {
      e.preventDefault();
      save();
    } else if (e.key === "Escape") {
      e.preventDefault();
      onComplete();
    }
  };

  return (
    <Input
      ref={inputRef}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={handleKeyDown}
      onBlur={save}
      onClick={(e) => e.stopPropagation()}
      className={className}
      disabled={renameMutation.isPending}
    />
  );
}
