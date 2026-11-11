import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError, register } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useRouter } from "../lib/router";

type Mode = "login" | "register";

function errorMessage(error: unknown, mode: Mode): string {
	if (error instanceof ApiError) {
		if (error.status === 401) return "Nieprawidłowy e-mail lub hasło.";
		if (error.status === 409) return "Konto z tym adresem już istnieje. Zaloguj się.";
		if (error.status === 422) return "Sprawdź adres e-mail: powinien mieć format nazwa@domena.pl.";
		if (error.status === 0) return "Brak połączenia z serwerem. Spróbuj ponownie za chwilę.";
	}
	return mode === "login"
		? "Nie udało się zalogować. Spróbuj ponownie."
		: "Nie udało się założyć konta. Spróbuj ponownie.";
}

/** Dozwolone są tylko ścieżki wewnętrzne - parametr ?next= nie może przenieść na inną stronę. */
function safeNext(next: string | null): string {
	return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export function Login() {
	const { login } = useAuth();
	const { search, navigate } = useRouter();
	const [mode, setMode] = useState<Mode>("login");
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [busy, setBusy] = useState(false);

	const tooShort = mode === "register" && password.length > 0 && password.length < 8;

	const submit = async (event: FormEvent) => {
		event.preventDefault();
		setError(null);
		if (mode === "register" && password.length < 8) {
			setError("Hasło musi mieć co najmniej 8 znaków.");
			return;
		}
		setBusy(true);
		try {
			if (mode === "register") await register(email.trim(), password);
			await login(email.trim(), password);
			navigate(safeNext(search.get("next")));
		} catch (caught) {
			setError(errorMessage(caught, mode));
		} finally {
			setBusy(false);
		}
	};

	return (
		<div className="container page page--narrow">
			<div className="auth">
				<div className="segmented" role="group" aria-label="Wybierz">
					<button
						type="button"
						className="segmented__btn"
						aria-pressed={mode === "login"}
						onClick={() => {
							setMode("login");
							setError(null);
						}}
					>
						Logowanie
					</button>
					<button
						type="button"
						className="segmented__btn"
						aria-pressed={mode === "register"}
						onClick={() => {
							setMode("register");
							setError(null);
						}}
					>
						Nowe konto
					</button>
				</div>

				<h1 className="auth__title">{mode === "login" ? "Zaloguj się" : "Załóż konto"}</h1>
				<p className="muted">
					{mode === "login"
						? "Po zalogowaniu rezerwacje trafiają na Twoje konto i widzisz je w „Moich biletach”."
						: "Wystarczy e-mail i hasło. Rezerwacje złożone na ten adres zobaczysz w „Moich biletach”."}
				</p>

				<form className="auth__form" onSubmit={submit} noValidate>
					<div className="field">
						<label className="field__label" htmlFor="auth-email">
							E-mail
						</label>
						<input
							id="auth-email"
							className="input"
							type="email"
							autoComplete="email"
							required
							value={email}
							onChange={(e) => setEmail(e.target.value)}
						/>
					</div>
					<div className="field">
						<label className="field__label" htmlFor="auth-password">
							Hasło
						</label>
						<input
							id="auth-password"
							className="input"
							type="password"
							autoComplete={mode === "login" ? "current-password" : "new-password"}
							required
							value={password}
							onChange={(e) => setPassword(e.target.value)}
							aria-invalid={tooShort ? true : undefined}
							aria-describedby={mode === "register" ? "auth-password-hint" : undefined}
						/>
						{mode === "register" && (
							<span className={tooShort ? "field__error" : "field__hint"} id="auth-password-hint">
								Co najmniej 8 znaków.
							</span>
						)}
					</div>
					{error && (
						<p className="field__error" role="alert">
							{error}
						</p>
					)}
					<button type="submit" className="btn btn--block" disabled={busy || !email || !password}>
						{busy ? "Chwileczkę…" : mode === "login" ? "Zaloguj się" : "Załóż konto"}
					</button>
				</form>
			</div>
		</div>
	);
}
