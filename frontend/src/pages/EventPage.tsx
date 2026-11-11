import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Stub } from "../components/Stub";
import type { StubPhase } from "../components/Stub";
import { ApiError, getEvent, getTicketStatus, newRequestId, requestTickets } from "../lib/api";
import type { EventItem } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDate, formatNumber, formatPrice, formatTime, ticketsWord } from "../lib/format";
import { Link } from "../lib/router";

const MAX_TICKETS = 8;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Bieżące zgłoszenie - trzymane w sessionStorage, żeby odświeżenie strony nie gubiło kwitu. */
type ActiveRequest = { requestId: string; quantity: number };
const storageKey = (eventId: string) => `ticketline.request.${eventId}`;

function readActive(eventId: string): ActiveRequest | null {
	try {
		const raw = window.sessionStorage.getItem(storageKey(eventId));
		return raw ? (JSON.parse(raw) as ActiveRequest) : null;
	} catch {
		return null;
	}
}

function writeActive(eventId: string, value: ActiveRequest | null) {
	try {
		if (value) window.sessionStorage.setItem(storageKey(eventId), JSON.stringify(value));
		else window.sessionStorage.removeItem(storageKey(eventId));
	} catch {
		// bez storage kwit działa do odświeżenia strony
	}
}

/** Odpytuje Booking API o status, coraz rzadziej (400 ms → maks. 3 s), aż do wyniku.
 *  Komponent używający hooka jest kluczowany po requestId, więc stan startuje od zera. */
function useTicketStatus(requestId: string) {
	const [phase, setPhase] = useState<StubPhase>("queued");
	const [reason, setReason] = useState<string | null>(null);
	const [offline, setOffline] = useState(false);

	useEffect(() => {
		let cancelled = false;
		let delay = 400;
		let timer = 0;

		const tick = async () => {
			try {
				const result = await getTicketStatus(requestId);
				if (cancelled) return;
				setOffline(false);
				if (result.status !== "queued") {
					// "duplicate" to ponownie wysłane to samo zgłoszenie: liczy się wynik pierwszego.
					setPhase(result.status);
					setReason(result.reason);
					return;
				}
			} catch (error) {
				if (cancelled) return;
				if (error instanceof ApiError && error.status === 404) {
					setPhase("expired");
					return;
				}
				setOffline(true);
			}
			delay = Math.min(delay * 1.5, 3000);
			timer = window.setTimeout(tick, delay);
		};

		timer = window.setTimeout(tick, delay);
		return () => {
			cancelled = true;
			window.clearTimeout(timer);
		};
	}, [requestId]);

	return { phase, reason, offline };
}

type ActiveProps = {
	event: EventItem;
	active: ActiveRequest;
	onSettled: () => void;
	onReset: () => void;
};

function ActiveBooking({ event, active, onSettled, onReset }: ActiveProps) {
	const status = useTicketStatus(active.requestId);
	const settled = status.phase !== "queued";

	useEffect(() => {
		if (settled) onSettled();
	}, [settled, onSettled]);

	return (
		<div className="booking">
			<Stub
				eventName={event.name}
				quantity={active.quantity}
				requestId={active.requestId}
				phase={status.phase}
				reason={status.reason}
				offline={status.offline}
			/>
			<div className="booking__after">
				{status.phase === "confirmed" && (
					<Link to="/moje-bilety" className="btn">
						Przejdź do moich biletów
					</Link>
				)}
				<button type="button" className="btn btn--quiet" disabled={!settled} onClick={onReset}>
					{settled ? "Nowa rezerwacja" : "Czekamy na wynik…"}
				</button>
			</div>
		</div>
	);
}

function BookingPanel({ event, onSettled }: { event: EventItem; onSettled: () => void }) {
	const { user } = useAuth();
	const [active, setActive] = useState<ActiveRequest | null>(() => readActive(event.id));
	const [quantity, setQuantity] = useState(1);
	const [email, setEmail] = useState("");
	const [emailError, setEmailError] = useState<string | null>(null);
	const [sendError, setSendError] = useState<string | null>(null);
	const [sending, setSending] = useState(false);

	const maxQuantity = Math.max(1, Math.min(MAX_TICKETS, event.available));
	const soldOut = event.available === 0;
	const buyerEmail = user?.email ?? email.trim();

	const submit = async (formEvent: FormEvent) => {
		formEvent.preventDefault();
		setSendError(null);
		if (!user && !EMAIL_PATTERN.test(buyerEmail)) {
			setEmailError("Podaj adres e-mail w formacie nazwa@domena.pl.");
			return;
		}
		setEmailError(null);
		setSending(true);
		const requestId = newRequestId();
		try {
			await requestTickets({ event_id: event.id, quantity, email: buyerEmail, request_id: requestId });
			const next = { requestId, quantity };
			writeActive(event.id, next);
			setActive(next);
		} catch (error) {
			setSendError(
				error instanceof ApiError && error.status === 503
					? "Kolejka jest chwilowo niedostępna. Zgłoszenie nie zostało wysłane, spróbuj ponownie za chwilę."
					: "Nie udało się wysłać zgłoszenia. Sprawdź połączenie i spróbuj ponownie.",
			);
		} finally {
			setSending(false);
		}
	};

	if (active) {
		return (
			<ActiveBooking
				key={active.requestId}
				event={event}
				active={active}
				onSettled={onSettled}
				onReset={() => {
					writeActive(event.id, null);
					setActive(null);
					setQuantity(1);
				}}
			/>
		);
	}

	return (
		<form className="booking booking__form" onSubmit={submit} noValidate>
			<div className="booking__row">
				<span className="field__label" id="qty-label">
					Liczba biletów
				</span>
				<div className="stepper" role="group" aria-labelledby="qty-label">
					<button
						type="button"
						className="stepper__btn"
						aria-label="Mniej biletów"
						disabled={soldOut || quantity <= 1}
						onClick={() => setQuantity((value) => Math.max(1, value - 1))}
					>
						−
					</button>
					<output className="stepper__value" aria-live="polite">
						{quantity}
					</output>
					<button
						type="button"
						className="stepper__btn"
						aria-label="Więcej biletów"
						disabled={soldOut || quantity >= maxQuantity}
						onClick={() => setQuantity((value) => Math.min(maxQuantity, value + 1))}
					>
						+
					</button>
				</div>
			</div>
			<p className="field__hint">Najwyżej {MAX_TICKETS} biletów w jednej rezerwacji.</p>

			{user ? (
				<p className="small muted">
					Bilety trafią na konto <strong className="booking__email">{user.email}</strong>.
				</p>
			) : (
				<div className="field">
					<label className="field__label" htmlFor="buyer-email">
						E-mail
					</label>
					<input
						id="buyer-email"
						className="input"
						type="email"
						autoComplete="email"
						placeholder="ty@przyklad.pl"
						value={email}
						onChange={(e) => setEmail(e.target.value)}
						aria-invalid={emailError ? true : undefined}
						aria-describedby={emailError ? "buyer-email-error" : "buyer-email-hint"}
						disabled={soldOut}
					/>
					{emailError ? (
						<span className="field__error" id="buyer-email-error">
							{emailError}
						</span>
					) : (
						<span className="field__hint" id="buyer-email-hint">
							Na ten adres zapiszemy rezerwację. <Link to="/logowanie" className="link">Zaloguj się</Link>,
							żeby widzieć ją w „Moich biletach”.
						</span>
					)}
				</div>
			)}

			<div className="booking__total">
				<span className="muted">Razem</span>
				<strong>{formatPrice(event.price * quantity)}</strong>
			</div>

			{sendError && (
				<p className="field__error" role="alert">
					{sendError}
				</p>
			)}

			<button type="submit" className="btn btn--block" disabled={soldOut || sending}>
				{soldOut
					? "Wyprzedane"
					: sending
						? "Wysyłamy zgłoszenie…"
						: `Zarezerwuj ${quantity} ${ticketsWord(quantity)}`}
			</button>
		</form>
	);
}

type Load = { state: "loading" } | { state: "missing" } | { state: "error" } | { state: "ready"; event: EventItem };

export function EventPage({ eventId }: { eventId: string }) {
	const [load, setLoad] = useState<Load>({ state: "loading" });

	const fetchEvent = useCallback(() => {
		getEvent(eventId)
			.then((event) => setLoad({ state: "ready", event }))
			.catch((error: unknown) =>
				setLoad({ state: error instanceof ApiError && error.status === 404 ? "missing" : "error" }),
			);
	}, [eventId]);

	useEffect(fetchEvent, [fetchEvent]);

	return (
		<div className="container page">
			<Link to="/" className="link small back-link">
				← Wszystkie wydarzenia
			</Link>

			{load.state === "loading" && <p className="muted">Wczytujemy wydarzenie…</p>}
			{load.state === "missing" && (
				<div className="notice">
					<p>Nie ma takiego wydarzenia. Mogło zostać usunięte albo link jest niepełny.</p>
				</div>
			)}
			{load.state === "error" && (
				<div className="notice notice--error" role="alert">
					<p>Nie możemy teraz pobrać wydarzenia. Spróbuj ponownie za chwilę.</p>
					<button type="button" className="btn btn--quiet" onClick={fetchEvent}>
						Spróbuj ponownie
					</button>
				</div>
			)}

			{load.state === "ready" && (
				<div className="event-detail">
					<article className="event-detail__info">
						<span className="label">{load.event.city}</span>
						<h1 className="event-detail__title">{load.event.name}</h1>
						<dl className="facts">
							<div>
								<dt>Data</dt>
								<dd>{formatDate(load.event.starts_at)}</dd>
							</div>
							<div>
								<dt>Godzina</dt>
								<dd>{formatTime(load.event.starts_at)}</dd>
							</div>
							<div>
								<dt>Miejsce</dt>
								<dd>
									{load.event.venue}, {load.event.city}
								</dd>
							</div>
							<div>
								<dt>Wolne miejsca</dt>
								<dd>
									{load.event.available === 0
										? "Wyprzedane"
										: `${formatNumber(load.event.available)} z ${formatNumber(load.event.capacity)}`}
								</dd>
							</div>
							<div>
								<dt>Cena biletu</dt>
								<dd>{formatPrice(load.event.price)}</dd>
							</div>
						</dl>
						<div className="how">
							<h2 className="how__title">Jak przebiega rezerwacja</h2>
							<p className="muted">
								Po kliknięciu zgłoszenie od razu trafia do kolejki i dostaje swój kwit. Kolejka
								przyjmuje każdy szczyt ruchu, a miejsca są przydzielane po kolei, jedno zgłoszenie
								po drugim, więc nikt nie dostanie miejsca, którego już nie ma.
							</p>
							<Link to="/od-kulis" className="link small">
								Zobacz, co dzieje się od kulis
							</Link>
						</div>
					</article>
					<aside className="event-detail__booking" aria-label="Rezerwacja">
						<BookingPanel event={load.event} onSettled={fetchEvent} />
					</aside>
				</div>
			)}
		</div>
	);
}
