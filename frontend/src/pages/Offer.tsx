import { useCallback, useEffect, useState } from "react";
import { getEvents } from "../lib/api";
import type { EventItem } from "../lib/api";
import { dateParts, formatNumber, formatPrice, formatTime, plural } from "../lib/format";
import { Link } from "../lib/router";

type Load = { state: "loading" } | { state: "error" } | { state: "ready"; events: EventItem[] };

function EventRow({ event }: { event: EventItem }) {
	const date = dateParts(event.starts_at);
	const soldOut = event.available === 0;
	return (
		<li>
			<Link to={`/wydarzenie/${encodeURIComponent(event.id)}`} className="event-row">
				<time className="event-row__date" dateTime={event.starts_at}>
					<span className="event-row__day">{date.day}</span>
					<span className="event-row__month">
						{date.month} {date.year}
					</span>
					<span className="event-row__weekday">
						{date.weekday}, {formatTime(event.starts_at)}
					</span>
				</time>
				<span className="event-row__main">
					<span className="event-row__name">{event.name}</span>
					<span className="event-row__place">
						{event.venue}, {event.city}
					</span>
				</span>
				<span className="event-row__avail">
					{soldOut ? (
						<span className="pill pill--no">Wyprzedane</span>
					) : (
						<>
							<strong>{formatNumber(event.available)}</strong>
							<span className="muted"> z {formatNumber(event.capacity)} wolnych</span>
						</>
					)}
				</span>
				<span className="event-row__price">{formatPrice(event.price)}</span>
				<span className="event-row__cta" aria-hidden="true">
					{soldOut ? "Szczegóły" : "Wybierz bilety"}
				</span>
			</Link>
		</li>
	);
}

export function Offer() {
	const [load, setLoad] = useState<Load>({ state: "loading" });

	const fetchEvents = useCallback(() => {
		getEvents()
			.then((events) => setLoad({ state: "ready", events }))
			.catch(() => setLoad({ state: "error" }));
	}, []);

	useEffect(fetchEvents, [fetchEvents]);

	return (
		<div className="container page">
			<section className="hero" aria-labelledby="hero-title">
				<h1 id="hero-title" className="hero__title">
					Bilety bez wyścigu
				</h1>
				<p className="hero__lead">
					Każde zgłoszenie dostaje miejsce w kolejce i jasną odpowiedź. Nikt nie dostaje miejsca,
					którego nie ma, i żadne zgłoszenie nie znika po drodze.
				</p>
			</section>

			<section className="offer" aria-labelledby="offer-title">
				<div className="section-head">
					<h2 id="offer-title">Wydarzenia</h2>
					{load.state === "ready" && (
						<span className="muted small">
							{load.events.length}{" "}
							{plural(load.events.length, "wydarzenie", "wydarzenia", "wydarzeń")}
						</span>
					)}
				</div>

				{load.state === "loading" && <p className="muted">Wczytujemy ofertę…</p>}

				{load.state === "error" && (
					<div className="notice notice--error" role="alert">
						<p>Nie możemy teraz pobrać oferty. Sprawdź połączenie i spróbuj ponownie.</p>
						<button
							type="button"
							className="btn btn--quiet"
							onClick={() => {
								setLoad({ state: "loading" });
								fetchEvents();
							}}
						>
							Spróbuj ponownie
						</button>
					</div>
				)}

				{load.state === "ready" && load.events.length === 0 && (
					<p className="muted">Na razie nie ma żadnych wydarzeń w sprzedaży.</p>
				)}

				{load.state === "ready" && load.events.length > 0 && (
					<ul className="event-list">
						{load.events.map((event) => (
							<EventRow key={event.id} event={event} />
						))}
					</ul>
				)}
			</section>
		</div>
	);
}
