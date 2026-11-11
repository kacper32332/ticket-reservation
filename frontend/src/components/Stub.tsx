// Kwit rezerwacji - powierzchnia sygnaturowa. Wszystkie stany są wyrenderowane
// w jednej komórce siatki i przenikają się w CSS (wejście i wyjście w 240 ms),
// więc wysokość kwitu nie skacze przy zmianie stanu.
import { ticketsWord } from "../lib/format";

export type StubPhase = "queued" | "confirmed" | "rejected" | "expired";

const REJECT_COPY: Record<string, { title: string; text: string }> = {
	sold_out: {
		title: "Wyprzedane",
		text: "Miejsca skończyły się, zanim przyszła Twoja kolej. Nic nie zostało zarezerwowane.",
	},
	event_not_found: {
		title: "Nie znaleziono wydarzenia",
		text: "To wydarzenie nie istnieje albo zostało usunięte. Nic nie zostało zarezerwowane.",
	},
	processing_failed: {
		title: "Nie udało się przetworzyć",
		text: "Zgłoszenie nie przeszło przetwarzania. Nic nie zostało zarezerwowane, możesz spróbować ponownie.",
	},
};

const FALLBACK_REJECT = {
	title: "Odrzucone",
	text: "Rezerwacja nie doszła do skutku. Nic nie zostało zarezerwowane.",
};

type Props = {
	eventName: string;
	quantity: number;
	requestId: string;
	phase: StubPhase;
	reason: string | null;
	/** brak połączenia podczas odpytywania o status */
	offline: boolean;
};

export function Stub({ eventName, quantity, requestId, phase, reason, offline }: Props) {
	const reject = (reason && REJECT_COPY[reason]) || FALLBACK_REJECT;
	const state = (name: StubPhase) => ({
		className: `stub__state stub__state--${name}${phase === name ? " is-active" : ""}`,
		"aria-hidden": phase !== name,
	});

	return (
		<section className="stub" aria-label="Kwit rezerwacji">
			<div className="stub__top">
				<span className="label">Kwit rezerwacji</span>
				<strong className="stub__title">
					{eventName} · {quantity} {ticketsWord(quantity)}
				</strong>
				<span className="mono muted stub__id">{requestId}</span>
			</div>
			<div className="stub__perf" aria-hidden="true" />
			<div className="stub__states" aria-live="polite">
				<div {...state("queued")}>
					<p className="stub__state-title">W kolejce</p>
					<div className="stub__track" aria-hidden="true">
						<i />
					</div>
					<p className="small muted">
						{offline
							? "Chwilowo nie mamy połączenia z serwerem. Zgłoszenie jest już w kolejce, sprawdzamy dalej."
							: "Zgłoszenie przyjęte. Wynik pojawi się tutaj, zwykle w ciągu kilku sekund."}
					</p>
				</div>
				<div {...state("confirmed")}>
					<p className="stub__state-title stub__state-title--ok">
						<svg className="stub__stamp" viewBox="0 0 22 22" aria-hidden="true">
							<circle cx="11" cy="11" r="10" />
							<path d="M6.5 11.5l3 3 6-6.5" />
						</svg>
						Potwierdzone
					</p>
					<p className="small muted">Bilety są Twoje. Znajdziesz je w „Moich biletach”.</p>
				</div>
				<div {...state("rejected")}>
					<p className="stub__state-title stub__state-title--no">{reject.title}</p>
					<p className="small muted">{reject.text}</p>
				</div>
				<div {...state("expired")}>
					<p className="stub__state-title">Status wygasł</p>
					<p className="small muted">
						Wynik tego zgłoszenia nie jest już dostępny. Jeśli rezerwacja się udała, zobaczysz ją
						w „Moich biletach”.
					</p>
				</div>
			</div>
		</section>
	);
}
