import { useEffect, useState } from "react";
import "./App.css";

type Event = {
	id: string;
	name: string;
	venue: string;
	date: string;
	city: string;
	status: string;
	sold: number;
	capacity: number;
	price: number;
	accent: string;
};

type Metrics = {
	queue_depth: number;
	events_processed: number;
	tickets_sold: number;
	capacity: number;
};

const fallbackEvents: Event[] = [
	{
		id: "evt-001",
		name: "The Weeknd",
		venue: "National Stadium",
		date: "24 Oct 2026",
		city: "Warsaw",
		status: "On sale",
		sold: 18420,
		capacity: 30000,
		price: 89,
		accent: "coral",
	},
	{
		id: "evt-002",
		name: "Open'er Festival",
		venue: "Gdynia-Kosakowo Airport",
		date: "1–4 Jul 2026",
		city: "Gdynia",
		status: "On sale",
		sold: 41600,
		capacity: 60000,
		price: 149,
		accent: "mint",
	},
	{
		id: "evt-003",
		name: "Formula E Berlin",
		venue: "Tempelhof Circuit",
		date: "12 Sep 2026",
		city: "Berlin",
		status: "Low stock",
		sold: 19750,
		capacity: 22000,
		price: 119,
		accent: "yellow",
	},
];

const formatNumber = (value: number) =>
	new Intl.NumberFormat("en-US").format(value);

function App() {
	const [events, setEvents] = useState<Event[]>(fallbackEvents);
	const [metrics, setMetrics] = useState<Metrics>({
		queue_depth: 0,
		events_processed: 0,
		tickets_sold: 79770,
		capacity: 112000,
	});
	const [activeTab, setActiveTab] = useState("Overview");
	const [notice, setNotice] = useState("");

	useEffect(() => {
		const load = async () => {
			try {
				const [eventResponse, metricsResponse] = await Promise.all([
					fetch("http://localhost:8000/api/events"),
					fetch("http://localhost:8000/api/metrics"),
				]);
				if (eventResponse.ok) setEvents(await eventResponse.json());
				if (metricsResponse.ok)
					setMetrics(await metricsResponse.json());
			} catch {
				setNotice(
					"Demo data active · connect the API to see live traffic",
				);
			}
		};
		void load();
	}, []);

	const queueTest = async () => {
		try {
			const response = await fetch(
				"http://localhost:8000/api/ticket-requests",
				{
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						event_id: events[0].id,
						quantity: 2,
						email: "ops@ticketline.test",
					}),
				},
			);
			if (!response.ok) throw new Error();
			setNotice("Request accepted · worker has it in the queue");
			setMetrics((current) => ({
				...current,
				queue_depth: current.queue_depth + 1,
			}));
		} catch {
			setNotice("Queue is offline · start Redis and the booking API");
		}
	};

	return (
		<div className="shell">
			<aside className="sidebar">
				<div className="brand">
					<span className="brand-mark">T</span>
					<span>ticketline</span>
				</div>
				<div className="workspace-label">Workspace</div>
				<div className="workspace">
					<span className="workspace-dot" /> Operations{" "}
					<span className="chevron">⌄</span>
				</div>
				<nav>
					{["Overview", "Events", "Orders", "Customers"].map(
						(tab, index) => (
							<button
								className={
									activeTab === tab
										? "nav-item active"
										: "nav-item"
								}
								onClick={() => setActiveTab(tab)}
								key={tab}
							>
								<span className="nav-icon">
									{["⌂", "▦", "↗", "♙"][index]}
								</span>
								{tab}
							</button>
						),
					)}
				</nav>
				<div className="sidebar-bottom">
					<button className="nav-item">
						<span className="nav-icon">⚙</span>Settings
					</button>
					<div className="profile">
						<div className="avatar">KM</div>
						<div>
							<strong>Kacper M.</strong>
							<small>Administrator</small>
						</div>
						<span className="more">•••</span>
					</div>
				</div>
			</aside>

			<main className="main-content">
				<header className="topbar">
					<div className="crumb">
						<span>Operations</span>
						<b>/</b>
						{activeTab}
					</div>
					<div className="top-actions">
						<span className="system-status">
							<i /> All systems operational
						</span>
						<button className="icon-button">?</button>
						<button className="icon-button">⌕</button>
						<button className="notification">
							♢<b>3</b>
						</button>
					</div>
				</header>
				<section className="page-heading">
					<div>
						<p className="eyebrow">Saturday, 19 September 2026</p>
						<h1>
							Good morning, Kacper <span>✦</span>
						</h1>
						<p className="subheading">
							Here’s what’s happening across your events today.
						</p>
					</div>
					<button className="primary-action" onClick={queueTest}>
						<span>＋</span> Simulate ticket request
					</button>
				</section>
				{notice && (
					<div className="notice">
						{notice}
						<button onClick={() => setNotice("")}>×</button>
					</div>
				)}

				<section className="metric-grid">
					<article className="metric-card">
						<div className="metric-top">
							<span>Gross sales</span>
							<span className="trend up">↗ 12.8%</span>
						</div>
						<strong>
							€{formatNumber(metrics.tickets_sold * 112)}
						</strong>
						<small>vs. €7.9M last period</small>
						<div className="sparkline coral-line">
							<i />
							<i />
							<i />
							<i />
							<i />
							<i />
							<i />
							<i />
						</div>
					</article>
					<article className="metric-card">
						<div className="metric-top">
							<span>Tickets sold</span>
							<span className="trend up">↗ 8.4%</span>
						</div>
						<strong>{formatNumber(metrics.tickets_sold)}</strong>
						<small>
							{formatNumber(
								metrics.capacity - metrics.tickets_sold,
							)}{" "}
							tickets remaining
						</small>
						<div className="sparkline mint-line">
							<i />
							<i />
							<i />
							<i />
							<i />
							<i />
							<i />
							<i />
						</div>
					</article>
					<article className="metric-card">
						<div className="metric-top">
							<span>Queue depth</span>
							<span className="live-pill">
								<i /> LIVE
							</span>
						</div>
						<strong>{formatNumber(metrics.queue_depth)}</strong>
						<small>Requests waiting for workers</small>
						<div className="queue-visual">
							<span>Worker pods</span>
							<b>04 / 04 active</b>
							<div>
								<i />
								<i />
								<i />
								<i />
							</div>
						</div>
					</article>
					<article className="metric-card">
						<div className="metric-top">
							<span>Conversion rate</span>
							<span className="trend down">↘ 1.2%</span>
						</div>
						<strong>7.24%</strong>
						<small>From 1.18M sessions</small>
						<div className="progress">
							<span style={{ width: "72%" }} />
						</div>
						<div className="progress-caption">
							<span>Target 8.0%</span>
							<b>90.5%</b>
						</div>
					</article>
				</section>

				<section className="content-grid">
					<div className="panel events-panel">
						<div className="panel-heading">
							<div>
								<h2>Live events</h2>
								<p>Inventory and sales at a glance</p>
							</div>
							<button
								className="text-button"
								onClick={() => setActiveTab("Events")}
							>
								View all events <span>→</span>
							</button>
						</div>
						<div className="table-wrap">
							<table>
								<thead>
									<tr>
										<th>Event</th>
										<th>Schedule</th>
										<th>Sales</th>
										<th>Fill rate</th>
										<th>Status</th>
									</tr>
								</thead>
								<tbody>
									{events.map((event) => (
										<tr key={event.id}>
											<td>
												<div className="event-cell">
													<span
														className={`event-art ${event.accent}`}
													>
														{event.name
															.slice(0, 2)
															.toUpperCase()}
													</span>
													<div>
														<strong>
															{event.name}
														</strong>
														<small>
															{event.venue}
														</small>
													</div>
												</div>
											</td>
											<td>
												<strong>{event.date}</strong>
												<small>{event.city}</small>
											</td>
											<td>
												<strong>
													€
													{formatNumber(
														event.sold *
															event.price,
													)}
												</strong>
												<small>
													{formatNumber(event.sold)}{" "}
													tickets
												</small>
											</td>
											<td>
												<div className="fill-cell">
													<div className="mini-progress">
														<span
															style={{
																width: `${Math.round((event.sold / event.capacity) * 100)}%`,
															}}
														/>
													</div>
													<small>
														{Math.round(
															(event.sold /
																event.capacity) *
																100,
														)}
														%
													</small>
												</div>
											</td>
											<td>
												<span
													className={`status ${event.status === "Low stock" ? "warning" : ""}`}
												>
													<i />
													{event.status}
												</span>
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					</div>
					<div className="panel activity-panel">
						<div className="panel-heading">
							<div>
								<h2>Activity</h2>
								<p>Latest system events</p>
							</div>
							<button className="dots">•••</button>
						</div>
						<div className="activity-list">
							<div>
								<span className="activity-icon green">✓</span>
								<p>
									<strong>Worker pod scaled up</strong>
									<small>worker-04 joined the pool</small>
								</p>
								<time>2m</time>
							</div>
							<div>
								<span className="activity-icon coral">↗</span>
								<p>
									<strong>New order spike</strong>
									<small>Formula E Berlin · 42 tickets</small>
								</p>
								<time>8m</time>
							</div>
							<div>
								<span className="activity-icon yellow">!</span>
								<p>
									<strong>Inventory alert</strong>
									<small>Formula E Berlin below 10%</small>
								</p>
								<time>24m</time>
							</div>
							<div>
								<span className="activity-icon blue">✦</span>
								<p>
									<strong>Event published</strong>
									<small>Open'er Festival is now live</small>
								</p>
								<time>1h</time>
							</div>
						</div>
						<button className="activity-footer">
							Open activity log <span>→</span>
						</button>
					</div>
				</section>
				<footer className="footer">
					<span>
						Ticketline Control Room <b>·</b> v0.1.0
					</span>
					<span>
						<i /> Redis connected <b>·</b> Last sync just now
					</span>
				</footer>
			</main>
		</div>
	);
}

export default App;
