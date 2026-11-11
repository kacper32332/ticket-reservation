import type { ReactNode } from "react";
import { useAuth } from "../lib/auth";
import { Link, useRouter } from "../lib/router";

function Header() {
	const { user, logout } = useAuth();
	const { navigate } = useRouter();

	return (
		<header className="site-header">
			<div className="container site-header__inner">
				<Link to="/" className="brand" aria-label="Ticketline, strona główna">
					<svg className="brand__mark" viewBox="0 0 24 24" aria-hidden="true">
						<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h15A1.5 1.5 0 0 1 21 6.5V9a3 3 0 0 0 0 6v2.5a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5V15a3 3 0 0 0 0-6Z" />
						<path d="M15 5v14" strokeDasharray="2 2" />
					</svg>
					<span>Ticketline</span>
				</Link>
				<nav className="site-nav" aria-label="Główna nawigacja">
					<Link to="/" className="site-nav__link">
						Wydarzenia
					</Link>
					<Link to="/moje-bilety" className="site-nav__link">
						Moje bilety
					</Link>
					<Link to="/od-kulis" matchPrefix className="site-nav__link">
						Od kulis
					</Link>
					{user?.is_admin && (
						<Link to="/admin" className="site-nav__link">
							Dodaj wydarzenie
						</Link>
					)}
				</nav>
				<div className="site-account">
					{user ? (
						<>
							<span className="site-account__email" title={user.email}>
								{user.email}
							</span>
							<button
								type="button"
								className="btn btn--quiet site-account__btn"
								onClick={() => {
									logout();
									navigate("/");
								}}
							>
								Wyloguj
							</button>
						</>
					) : (
						<Link to="/logowanie" className="btn btn--quiet site-account__btn">
							Zaloguj się
						</Link>
					)}
				</div>
			</div>
		</header>
	);
}

function Footer() {
	return (
		<footer className="site-footer">
			<div className="container site-footer__inner">
				<p className="small muted">
					Ticketline to projekt inżynierski: system rezerwacji, który przyjmuje nagły szczyt ruchu
					przez kolejkę i nie sprzedaje więcej miejsc, niż ma.
				</p>
				<Link to="/od-kulis" className="link small">
					Zobacz, jak działa od kulis
				</Link>
			</div>
		</footer>
	);
}

export function Layout({ children }: { children: ReactNode }) {
	return (
		<div className="site">
			<a className="skip-link" href="#main">
				Przejdź do treści
			</a>
			<Header />
			<main id="main" className="site-main">
				{children}
			</main>
			<Footer />
		</div>
	);
}
