import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginUser, registerUser, saveSession } from "../lib/api";

export default function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const form = new FormData(e.currentTarget);
    try {
      if (mode === "register") {
        const data = await registerUser({
          email: String(form.get("email")),
          password: String(form.get("password")),
          full_name: String(form.get("full_name")),
          organization_name: String(form.get("organization_name")),
        });
        saveSession(data.access_token, data.organization_id);
      } else {
        const data = await loginUser({
          email: String(form.get("email")),
          password: String(form.get("password")),
        });
        saveSession(data.access_token, data.organization_id);
      }
      navigate("/");
    } catch {
      setError("Authentication failed. Check your credentials and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 p-6">
      <div className="w-full max-w-md rounded-2xl bg-white border border-slate-200 shadow-sm p-8">
        <h1 className="text-2xl font-semibold mb-1">AQREM</h1>
        <p className="text-slate-600 mb-6">Evidence-backed questionnaire responses</p>
        <div className="flex gap-2 mb-6">
          <button
            type="button"
            className={`flex-1 rounded-lg py-2 text-sm ${mode === "login" ? "bg-slate-900 text-white" : "bg-slate-100"}`}
            onClick={() => setMode("login")}
          >
            Sign in
          </button>
          <button
            type="button"
            className={`flex-1 rounded-lg py-2 text-sm ${mode === "register" ? "bg-slate-900 text-white" : "bg-slate-100"}`}
            onClick={() => setMode("register")}
          >
            Register
          </button>
        </div>
        <form className="space-y-3" onSubmit={onSubmit}>
          {mode === "register" && (
            <>
              <input
                name="full_name"
                placeholder="Full name"
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                required
              />
              <input
                name="organization_name"
                placeholder="Organization name"
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                required
              />
            </>
          )}
          <input
            name="email"
            type="email"
            placeholder="Email"
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
            required
          />
          <input
            name="password"
            type="password"
            placeholder="Password"
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
            required
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-slate-900 text-white py-2.5 font-medium disabled:opacity-60"
          >
            {loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}
