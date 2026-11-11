import "./App.css";
import { Layout } from "./components/Layout";
import { AuthProvider } from "./lib/auth";
import { Link, RouterProvider, useRouter } from "./lib/router";
import { EventPage } from "./pages/EventPage";
import { Login } from "./pages/Login";
import { MyTickets } from "./pages/MyTickets";
import { Offer } from "./pages/Offer";

function NotFound() {
	return (
		<div className="container page">
			<div className="notice">
				<p>Nie ma takiej strony.</p>
				<Link to="/" className="btn">
					Wróć do wydarzeń
				</Link>
			</div>
		</div>
	);
}

// Tymczasowo: strony z kolejnego etapu (admin, od kulis).
function Upcoming({ title }: { title: string }) {
	return (
		<div className="container page">
			<h1>{title}</h1>
			<p className="muted">Ta strona powstanie w następnym kroku.</p>
		</div>
	);
}

function Routes() {
	const { path } = useRouter();

	if (path === "/") return <Offer />;
	if (path.startsWith("/wydarzenie/")) {
		const id = decodeURIComponent(path.slice("/wydarzenie/".length));
		return <EventPage key={id} eventId={id} />;
	}
	if (path === "/moje-bilety") return <MyTickets />;
	if (path === "/logowanie") return <Login />;
	if (path === "/admin") return <Upcoming title="Dodaj wydarzenie" />;
	if (path === "/od-kulis") return <Upcoming title="Od kulis" />;
	if (path === "/od-kulis/kolejka") return <Upcoming title="Kolejka na żywo" />;
	return <NotFound />;
}

export default function App() {
	return (
		<RouterProvider>
			<AuthProvider>
				<Layout>
					<Routes />
				</Layout>
			</AuthProvider>
		</RouterProvider>
	);
}
