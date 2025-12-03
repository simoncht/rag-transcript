"use client";

import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { MainLayout } from "@/components/layout/MainLayout";
import { conversationsApi } from "@/lib/api/conversations";
import { Send, Loader2, ExternalLink } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import ReactMarkdown from "react-markdown";

export default function ConversationPage() {
  const params = useParams();
  const conversationId = params.id as string;
  const [message, setMessage] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const { data: conversation, isLoading } = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => conversationsApi.get(conversationId),
    refetchInterval: 5000,
  });

  const sendMessageMutation = useMutation({
    mutationFn: (messageText: string) =>
      conversationsApi.sendMessage(conversationId, messageText, false),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
      setMessage("");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim()) {
      sendMessageMutation.mutate(message.trim());
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation?.messages]);

  const formatTimestamp = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}:${secs.toString().padStart(2, "0")}`;
  };

  if (isLoading) {
    return (
      <MainLayout>
        <div className="flex justify-center items-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        </div>
      </MainLayout>
    );
  }

  if (!conversation) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <p className="text-gray-500">Conversation not found</p>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="h-[calc(100vh-8rem)] flex flex-col">
        <div className="bg-white shadow sm:rounded-t-lg p-4 border-b">
          <h1 className="text-xl font-semibold text-gray-900">
            {conversation.title}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {conversation.selected_video_ids.length} video
            {conversation.selected_video_ids.length !== 1 ? "s" : ""} •{" "}
            {conversation.message_count} message
            {conversation.message_count !== 1 ? "s" : ""}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto bg-gray-50 p-4 space-y-4">
          {conversation.messages.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-500">
                No messages yet. Start a conversation by asking a question below.
              </p>
            </div>
          ) : (
            conversation.messages.map((msg, index) => {
              const isUser = msg.role === "user";
              const messageData =
                !isUser && index > 0
                  ? (conversation.messages[index] as any)
                  : null;

              return (
                <div
                  key={msg.id}
                  className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-3xl ${
                      isUser
                        ? "bg-blue-600 text-white"
                        : "bg-white border border-gray-200"
                    } rounded-lg p-4 shadow-sm`}
                  >
                    <div
                      className={`text-sm ${
                        isUser ? "text-white" : "text-gray-900"
                      }`}
                    >
                      {isUser ? (
                        <p>{msg.content}</p>
                      ) : (
                        <ReactMarkdown className="prose prose-sm max-w-none">
                          {msg.content}
                        </ReactMarkdown>
                      )}
                    </div>

                    {!isUser && messageData?.chunk_references && (
                      <div className="mt-3 pt-3 border-t border-gray-200">
                        <p className="text-xs font-medium text-gray-500 mb-2">
                          Sources:
                        </p>
                        <div className="space-y-2">
                          {messageData.chunk_references.map(
                            (ref: any, idx: number) => (
                              <div
                                key={idx}
                                className="text-xs bg-gray-50 p-2 rounded"
                              >
                                <div className="flex items-center justify-between mb-1">
                                  <span className="font-medium text-gray-700">
                                    {ref.video_title}
                                  </span>
                                  <span className="text-gray-500">
                                    {ref.timestamp_display}
                                  </span>
                                </div>
                                <p className="text-gray-600 line-clamp-2">
                                  {ref.text_snippet}
                                </p>
                                <div className="mt-1 flex items-center justify-between">
                                  <span className="text-gray-500">
                                    Relevance: {(ref.relevance_score * 100).toFixed(1)}%
                                  </span>
                                  <a
                                    href={`#video-${ref.video_id}`}
                                    className="inline-flex items-center text-blue-600 hover:text-blue-800"
                                  >
                                    <ExternalLink className="w-3 h-3 mr-1" />
                                    View source
                                  </a>
                                </div>
                              </div>
                            )
                          )}
                        </div>
                      </div>
                    )}

                    <div
                      className={`mt-2 text-xs ${
                        isUser ? "text-blue-100" : "text-gray-500"
                      }`}
                    >
                      {formatDistanceToNow(new Date(msg.created_at))} ago
                      {!isUser && msg.response_time_seconds && (
                        <span className="ml-2">
                          • {msg.response_time_seconds.toFixed(1)}s
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="bg-white shadow sm:rounded-b-lg p-4 border-t">
          <form onSubmit={handleSubmit} className="flex space-x-3">
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Ask a question about the videos..."
              disabled={sendMessageMutation.isPending}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              disabled={!message.trim() || sendMessageMutation.isPending}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {sendMessageMutation.isPending ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </form>
          {sendMessageMutation.isPending && (
            <p className="mt-2 text-sm text-gray-500">
              Searching transcripts and generating response...
            </p>
          )}
        </div>
      </div>
    </MainLayout>
  );
}
