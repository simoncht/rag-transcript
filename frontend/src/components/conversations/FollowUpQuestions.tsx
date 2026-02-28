"use client";

import { Button } from "@/components/ui/button";

interface FollowUpQuestionsProps {
  questions: string[];
  onQuestionClick: (question: string) => void;
  disabled?: boolean;
}

export function FollowUpQuestions({ questions, onQuestionClick, disabled }: FollowUpQuestionsProps) {
  if (!questions || questions.length === 0) return null;

  return (
    <div className="mt-3">
      <p className="text-[11px] text-muted-foreground mb-2">Follow up:</p>
      <div className="flex flex-wrap gap-2">
        {questions.map((question, idx) => (
          <Button
            key={idx}
            variant="outline"
            size="sm"
            className="text-xs h-auto py-1.5 px-3 whitespace-normal text-left max-w-xs"
            onClick={() => onQuestionClick(question)}
            disabled={disabled}
          >
            {question}
          </Button>
        ))}
      </div>
    </div>
  );
}
