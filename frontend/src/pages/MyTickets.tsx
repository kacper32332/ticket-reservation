import { useEffect, useState } from "react";
import { getEvents, getMyBookings } from "../lib/api";
import type { Booking, EventItem } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDate, formatStamp, ticketsWord } from "../lib/format";
import { Link } from "../lib/router";

type Load =
	| { state: "loading" }
	| { state: "error" }
	| { state: "ready"; bookings: Booking[]; events: Map<string, EventItem> };

function TicketList({ token }: { token: string }) {
	const [load, setLoad] = useState<Load>({ state: "loading" });

	useEffect(() => {
		let cancelled = false;
		Promise.all([getMyBookings(token), getEvents()])
			.then(([bookings, events]) => {
				if (!cancelled) setLoad({ state: "ready", bookings, events: new Map(events.map((e) => [e.id, e])) });
			})
			.catch(() => {
				if (!cancelled) setLoad({ state: "error" });
			});
		return () => {
			cancelled = true;
		};
	}, [token]);

	if (load.state === "loading") return <p className="muted">Wczytujemy Twoje rezerwacje…</p>;
	if (load.state === "error")
		return (
			<div className="notice notice--error" role="alert">
				<p>Nie możemy teraz pobrać rezerwacji. Odśwież stronę za chwilę.</p>
			</div>
		);
	if (load.bookings.length === 0)
		return (
			<div className="notice">
				<p>Nie masz jeszcze żadnych rezerwacji.</p>
				<Link to="/" className="btn">
					Zobacz wydarzenia
				</Link>
			</div>
		);

	return (
		<ul className="ticket-list">
			{load.bookings.map((booking) => {
				const event = load.events.get(booking.event_id);
				const confirmed = booking.status === "confirmed";
				return (
					<li key={booking.request_id} className="ticket-row">
						<div className="ticket-row__main">
							<strong className="ticket-row__name">{event?.name ?? booking.event_id}</strong>
							<span className="small muted">
								{event ? `${formatDate(event.starts_at)} · ${event.venue}, ${event.city}` : "Wydarzenie usunięte z oferty"}
							</span>
						</div>
						<span className="ticket-row__qty">
							{booking.quantity} {ticketsWord(booking.quantity)}
						</span>
						<span className={`pill ${confirmed ? "pill--ok" : "pill--no"}`}>
							{confirmed ? "Potwierdzona" : "Odrzucona"}
						</span>
						<span className="small muted ticket-row__when">złożona {formatStamp(booking.created_at)}</span>
					</li>
				);
			})}
		</ul>
	);
}

export function MyTickets() {
	const { token, user, checking } = useAuth();

	return (
		<div className="container page">
			<div className="section-head">
				<h1>Moje bilety</h1>
				{user && <span className="small muted">{user.email}</span>}
			</div>
			{checking && <p className="muted">Sprawdzamy logowanie…</p>}
			{!checking && !token && (
				<div className="notice">
					<p>Zaloguj się, żeby zobaczyć rezerwacje złożone na Twój adres e-mail.</p>
					<Link to="/logowanie?next=/moje-bilety" className="btn">
						Zaloguj się
					</Link>
				</div>
			)}
			{!checking && token && <TicketList token={token} />}
		</div>
	);
}
