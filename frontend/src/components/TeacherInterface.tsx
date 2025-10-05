"use client";

import React, { useState } from "react";

interface TeacherInterfaceProps {
  documentId: string;
}

export function TeacherInterface({ documentId }: TeacherInterfaceProps) {
  const [sessionState, setSessionState] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState("");
  const [history, setHistory] = useState<
    Array<{
      explanation?: string;
      problem?: string;
      answer?: string;
      feedback?: string;
      isCorrect?: boolean;
    }>
  >([]);

  function getAuthHeader(): Record<string, string> {
    try {
      if (typeof window !== "undefined") {
        const token = localStorage.getItem("access_token");
        return token ? { Authorization: `Bearer ${token}` } : {};
      }
    } catch (err) {
      console.warn("Could not read token from localStorage", err);
    }
    return {};
  }

  const startSession = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/teacher/start`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeader(),
        } as HeadersInit,
        body: JSON.stringify({ document_id: parseInt(documentId, 10) }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`startSession failed: ${response.status} ${text}`);
      }

      const data = await response.json();
      setSessionState(data.session_state ?? {});
      setHistory([
        {
          explanation: data.explanation,
          problem: data.problem,
        },
      ]);
    } catch (error) {
      console.error("Failed to start session:", error);
      // optionally show UI error
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async () => {
    if (!answer.trim()) return;

    setLoading(true);
    try {
      const response = await fetch(`/api/teacher/answer`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeader(),
        } as HeadersInit,
        body: JSON.stringify({
          document_id: parseInt(documentId, 10),
          answer,
          session_state: sessionState,
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`submitAnswer failed: ${response.status} ${text}`);
      }

      const data = await response.json();

      // Update history
      setHistory((prev) => [
        ...prev,
        {
          answer: answer,
          feedback: data.feedback,
          isCorrect: data.is_correct,
        },
      ]);

      // If there's a next problem, add it
      if (data.next_problem) {
        setHistory((prev) => [
          ...prev,
          {
            explanation: data.next_explanation,
            problem: data.next_problem,
          },
        ]);
      }

      setSessionState(data.session_state ?? {});
      setAnswer("");
    } catch (error) {
      console.error("Failed to submit answer:", error);
    } finally {
      setLoading(false);
    }
  };

  if (!sessionState) {
    return (
      <div className="text-center p-8">
        <h3 className="text-xl font-semibold mb-4">
          Interactive Learning Mode
        </h3>
        <p className="text-gray-600 mb-6">
          An AI teacher will guide you through the material with adaptive
          lessons and practice problems.
        </p>
        <button
          onClick={startSession}
          disabled={loading}
          className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
        >
          {loading ? "Starting..." : "Start Learning Session"}
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-blue-50 p-4 border-b">
        <h3 className="font-semibold text-blue-900">
          {sessionState.topic ?? "Lesson"}
        </h3>
        <p className="text-sm text-blue-700 mt-1">
          Lesson {Number(sessionState.current_lesson ?? 0) + 1} of{" "}
          {Array.isArray(sessionState.lesson_plan)
            ? sessionState.lesson_plan.length
            : 1}
        </p>
      </div>

      {/* Chat History */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {history.map((item, idx) => (
          <div key={idx} className="space-y-2">
            {item.explanation && (
              <div className="bg-green-50 border-l-4 border-green-500 p-4">
                <h4 className="font-semibold text-green-900 mb-2">
                  Lesson Explanation
                </h4>
                <p className="text-gray-700 whitespace-pre-wrap">
                  {item.explanation}
                </p>
              </div>
            )}

            {item.problem && (
              <div className="bg-blue-50 border-l-4 border-blue-500 p-4">
                <h4 className="font-semibold text-blue-900 mb-2">
                  Practice Problem
                </h4>
                <p className="text-gray-700">{item.problem}</p>
              </div>
            )}

            {item.answer && (
              <div className="flex justify-end">
                <div className="bg-gray-200 rounded-lg px-4 py-2 max-w-[80%]">
                  <p className="text-gray-900">Your answer: {item.answer}</p>
                </div>
              </div>
            )}

            {item.feedback && (
              <div
                className={`border-l-4 p-4 ${
                  item.isCorrect
                    ? "bg-green-50 border-green-500"
                    : "bg-yellow-50 border-yellow-500"
                }`}
              >
                <h4
                  className={`font-semibold mb-2 ${
                    item.isCorrect ? "text-green-900" : "text-yellow-900"
                  }`}
                >
                  {item.isCorrect ? "✓ Correct!" : "→ Feedback"}
                </h4>
                <p className="text-gray-700 whitespace-pre-wrap">
                  {item.feedback}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Answer Input */}
      <div className="border-t p-4">
        <div className="flex space-x-2">
          <input
            type="text"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitAnswer()}
            placeholder="Type your answer..."
            className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
            disabled={loading}
          />
          <button
            onClick={submitAnswer}
            disabled={loading || !answer.trim()}
            className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            {loading ? "Checking..." : "Submit"}
          </button>
        </div>
      </div>
    </div>
  );
}
