import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  fetchQuestionnaireQuestions,
  generateQuestionnaireAnswers,
  loadSession,
} from "../lib/api";

type Question = {
  id: string;
  external_id: string;
  section?: string;
  text: string;
};

export default function QuestionnaireDetailPage() {
  const { questionnaireId } = useParams();
  const session = loadSession();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session || !questionnaireId) return;
    fetchQuestionnaireQuestions(session, questionnaireId).then(setQuestions);
  }, [session, questionnaireId]);

  async function onGenerateAll() {
    if (!session || !questionnaireId) return;
    setMessage("Generating answers…");
    try {
      const result = await generateQuestionnaireAnswers(session, questionnaireId);
      setMessage(`Generated ${result.generated} answers (${result.insufficient} insufficient evidence).`);
    } catch {
      setMessage("Generation failed.");
    }
  }

  if (!session) return <p>Please sign in.</p>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">Questionnaire</h1>
          <p className="text-slate-600 text-sm">{questionnaireId}</p>
        </div>
        <button
          onClick={onGenerateAll}
          className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium"
        >
          Generate all answers
        </button>
      </div>
      {message && <p className="mb-4 text-sm text-slate-700">{message}</p>}
      <div className="space-y-3">
        {questions.map((q) => (
          <div key={q.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-xs text-slate-500 mb-1">
              {q.external_id}
              {q.section ? ` · ${q.section}` : ""}
            </div>
            <p className="font-medium mb-3">{q.text}</p>
            <Link
              to={`/questionnaires/${questionnaireId}/questions/${q.id}/review`}
              className="text-sm text-blue-600 hover:underline"
            >
              Open review workspace
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
