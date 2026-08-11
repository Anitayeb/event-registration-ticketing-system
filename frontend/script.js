/* ==========================================================================
   RegEvents — Event Registration & Ticketing
   Wires the static markup in index.html to all 4 backend endpoints:
     GET    /events                  → hero stats, featured card, event list
     POST   /register                → registration form + boarding pass
     GET    /registrations/{email}   → "My Tickets" lookup section
     DELETE /registration/{id}       → cancel button on each looked-up ticket
   ========================================================================== */

/* --------------------------------------------------------------------
   0. Configuration
   -------------------------------------------------------------------- */

// config.js supplies the deployed URL; the fallback supports sam local start-api.
const API_BASE = window.APP_CONFIG?.apiBaseUrl || "";

/* --------------------------------------------------------------------
   1. Small helpers
   -------------------------------------------------------------------- */

const $ = (id) => document.getElementById(id);

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function api(path, opts = {}) {
  if (!API_BASE) {
    throw new Error("Set apiBaseUrl in frontend/config.js to your API URL.");
  }
  const res = await fetch(API_BASE.replace(/\/$/, "") + path, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function formatDate(iso) {
  if (!iso) return "Date TBA";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

// Mirrors the backend's validation in lambdas/register.py — catches obvious
// mistakes client-side so the person isn't waiting on a round trip for them.
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PHONE_RE = /^\+?[\d\s\-()]{7,20}$/;

/* --------------------------------------------------------------------
   2. Event status logic
   Backend events have: eventId, name, date, capacity, registeredCount.
   "Limited" kicks in once an event is 80%+ full; "Sold out" once full;
   events without a capacity are always "Available".
   -------------------------------------------------------------------- */

function eventStatus(ev) {
  const capacity = ev.capacity;
  const count = ev.registeredCount ?? 0;
  if (capacity == null) return { key: "available", label: "Available" };
  const seatsLeft = capacity - count;
  if (seatsLeft <= 0) return { key: "soldout", label: "Sold out" };
  if (count / capacity >= 0.8) return { key: "limited", label: `${seatsLeft} left` };
  return { key: "available", label: `${seatsLeft} left` };
}

/* --------------------------------------------------------------------
   3. State
   -------------------------------------------------------------------- */

let allEvents = [];
let lastFocusedBeforeModal = null;

/* --------------------------------------------------------------------
   4. Loading & rendering events
   -------------------------------------------------------------------- */

async function loadEvents() {
  renderLoadingState();
  try {
    const data = await api("/events");
    allEvents = (data.events || []).slice().sort((a, b) => {
      return new Date(a.date || 0) - new Date(b.date || 0);
    });
  } catch (err) {
    renderLoadError(err.message);
    return;
  }
  renderStats();
  renderFeaturedAndList();
  populateEventSelect();
}

function renderLoadingState() {
  $("stat-open").textContent = "…";
  $("stat-seats").textContent = "…";
  $("stat-fill").textContent = "…";
  $("featured-event").innerHTML = `<p class="section-sub">Loading events…</p>`;
}

function renderLoadError(message) {
  $("featured-event").innerHTML = `<p class="section-sub">Could not load events — ${escapeHtml(message)}</p>`;
  $("events-grid").innerHTML = "";
}

function renderStats() {
  const openEvents = allEvents.filter((ev) => eventStatus(ev).key !== "soldout");
  const seatsLeft = allEvents.reduce((sum, ev) => {
    if (ev.capacity == null) return sum;
    return sum + Math.max(0, ev.capacity - (ev.registeredCount ?? 0));
  }, 0);

  const withCapacity = allEvents.filter((ev) => ev.capacity);
  const avgFill = withCapacity.length
    ? Math.round(
        (withCapacity.reduce((sum, ev) => sum + (ev.registeredCount ?? 0) / ev.capacity, 0) /
          withCapacity.length) *
          100
      )
    : 0;

  $("stat-open").textContent = openEvents.length;
  $("stat-seats").textContent = seatsLeft;
  $("stat-fill").textContent = `${avgFill}%`;
}

function renderFeaturedAndList() {
  const featuredEl = $("featured-event");
  const listEl = $("events-grid");

  if (!allEvents.length) {
    featuredEl.innerHTML = `<p class="section-sub">No events yet — check back soon.</p>`;
    listEl.innerHTML = "";
    return;
  }

  const [featured, ...rest] = allEvents;
  featuredEl.innerHTML = featuredCardHtml(featured);
  featuredEl.querySelector(".btn-card-register").addEventListener("click", () => jumpToRegister(featured.eventId));
  featuredEl.querySelector(".btn-view").addEventListener("click", () => openModal(featured.eventId));

  listEl.innerHTML = "";
  rest.forEach((ev) => {
    const li = document.createElement("li");
    li.innerHTML = eventRowHtml(ev);
    li.querySelector(".btn-card-register, .row-actions .btn-primary")?.addEventListener("click", () =>
      jumpToRegister(ev.eventId)
    );
    li.querySelector(".btn-view").addEventListener("click", () => openModal(ev.eventId));
    listEl.appendChild(li);
  });
}

function featuredCardHtml(ev) {
  const status = eventStatus(ev);
  const disabled = status.key === "soldout" ? "disabled" : "";
  return `
    <div class="featured-card">
      <span class="featured-tag">Featured</span>
      <div class="featured-body">
        <h3>${escapeHtml(ev.name || ev.eventId)}</h3>
        <p class="featured-meta">
          <span>${escapeHtml(formatDate(ev.date))}</span>
          <span>ID · ${escapeHtml(ev.eventId)}</span>
        </p>
        <p class="featured-desc">${escapeHtml(ev.description || "Details available on request.")}</p>
      </div>
      <div class="featured-actions">
        <span class="featured-seats">${escapeHtml(status.label)}</span>
        <div class="card-actions">
          <button type="button" class="btn btn-view">View details</button>
          <button type="button" class="btn btn-card-register" ${disabled}>Register</button>
        </div>
      </div>
    </div>
  `;
}

function eventRowHtml(ev) {
  const status = eventStatus(ev);
  const disabled = status.key === "soldout" ? "disabled" : "";
  return `
    <div class="event-row">
      <span class="row-accent row-accent--${status.key}" aria-hidden="true"></span>
      <div class="row-title">
        <h3>${escapeHtml(ev.name || ev.eventId)}</h3>
      </div>
      <p class="row-meta">
        <span>${escapeHtml(formatDate(ev.date))}</span>
        <span>ID · ${escapeHtml(ev.eventId)}</span>
      </p>
      <span class="row-seats">${escapeHtml(status.label)}</span>
      <div class="row-actions">
        <button type="button" class="btn btn-view">Details</button>
        <button type="button" class="btn btn-primary" ${disabled}>Register</button>
      </div>
    </div>
  `;
}

function jumpToRegister(eventId) {
  $("event-select").value = eventId;
  updatePreview();
  document.getElementById("register").scrollIntoView({ behavior: "smooth" });
  $("full-name").focus();
}

/* --------------------------------------------------------------------
   5. Registration form <select> population
   -------------------------------------------------------------------- */

function populateEventSelect() {
  const select = $("event-select");
  const current = select.value;
  select.innerHTML = `<option value="" disabled ${current ? "" : "selected"}>Choose an event&hellip;</option>`;
  allEvents.forEach((ev) => {
    const status = eventStatus(ev);
    const opt = document.createElement("option");
    opt.value = ev.eventId;
    opt.textContent = `${ev.name || ev.eventId} — ${formatDate(ev.date)}`;
    if (status.key === "soldout") {
      opt.disabled = true;
      opt.textContent += " (sold out)";
    }
    select.appendChild(opt);
  });
  if (current) select.value = current;
}

/* --------------------------------------------------------------------
   6. Live ticket preview
   -------------------------------------------------------------------- */

function updatePreview() {
  const ev = allEvents.find((e) => e.eventId === $("event-select").value);
  const name = $("full-name").value.trim();

  $("preview-event").textContent = ev ? ev.name || ev.eventId : "Select an event";
  $("preview-meta").textContent = ev ? `${formatDate(ev.date)} · ${ev.eventId}` : "—";
  $("preview-name").textContent = name || "Your name";

  const pill = $("preview-status");
  if (!ev) {
    pill.textContent = "Pending";
    pill.className = "status-pill status-pill--pending";
  } else {
    const status = eventStatus(ev);
    pill.textContent = status.key === "soldout" ? "Sold out" : "Ready to register";
    pill.className = `status-pill status-pill--${status.key === "soldout" ? "soldout" : "available"}`;
  }
}

/* --------------------------------------------------------------------
   7. Registration submit
   -------------------------------------------------------------------- */

function showFormError(message) {
  const el = $("form-error");
  if (!message) {
    el.hidden = true;
    el.textContent = "";
    return;
  }
  el.hidden = false;
  el.textContent = message;
}

async function handleRegisterSubmit(e) {
  e.preventDefault();
  showFormError("");

  const eventId = $("event-select").value;
  const name = $("full-name").value.trim();
  const email = $("email").value.trim();
  const phone = $("phone").value.trim(); // optional — stored server-side when provided

  if (!eventId) return showFormError("Please choose an event.");
  if (!name) return showFormError("Please enter your full name.");
  if (!email) return showFormError("Please enter your email address.");
  if (!EMAIL_RE.test(email)) return showFormError("Please enter a valid email address.");
  if (phone && !PHONE_RE.test(phone)) return showFormError("Please enter a valid phone number, or leave it blank.");

  const btn = $("submit-btn");
  btn.disabled = true;
  btn.classList.add("is-loading");

  try {
    const data = await api("/register", {
      method: "POST",
      body: JSON.stringify({ eventId, name, email, phone }),
    });
    showConfirmation(data.registration);
    await loadEvents(); // refresh counts/seat availability
  } catch (err) {
    showFormError(err.message);
  } finally {
    btn.disabled = false;
    btn.classList.remove("is-loading");
  }
}

function showConfirmation(registration) {
  const ev = allEvents.find((e) => e.eventId === registration.eventId);

  $("conf-event-name").textContent = ev ? ev.name || ev.eventId : registration.eventId;
  $("conf-attendee").textContent = registration.name;
  $("conf-email").textContent = registration.email;
  $("conf-date").textContent = formatDate(ev ? ev.date : null);
  $("conf-id").textContent = `GP-${registration.registrationId.slice(0, 8).toUpperCase()}`;

  $("registration-form").hidden = true;
  $("confirmation").hidden = false;
}

function resetRegistrationFlow() {
  $("registration-form").reset();
  $("registration-form").hidden = false;
  $("confirmation").hidden = true;
  showFormError("");
  updatePreview();
  document.getElementById("register").scrollIntoView({ behavior: "smooth" });
}

/* --------------------------------------------------------------------
   8. Modal (event details)
   -------------------------------------------------------------------- */

function openModal(eventId) {
  const ev = allEvents.find((e) => e.eventId === eventId);
  if (!ev) return;
  const status = eventStatus(ev);

  lastFocusedBeforeModal = document.activeElement;

  $("modal-title").textContent = ev.name || ev.eventId;
  $("modal-date").textContent = formatDate(ev.date);
  $("modal-time").textContent = ev.time || "TBA";
  $("modal-venue").textContent = ev.venue || "TBA";
  $("modal-seats").textContent = status.key === "soldout" ? "Sold out" : status.label;
  $("modal-description").textContent = ev.description || "No additional details provided for this event.";

  const badge = $("modal-badge");
  badge.textContent = status.key === "soldout" ? "Sold out" : status.key === "limited" ? "Filling up" : "Available";
  badge.className = `status-pill status-pill--${status.key}`;

  const registerBtn = $("modal-register-btn");
  registerBtn.disabled = status.key === "soldout";
  registerBtn.onclick = () => {
    closeModal();
    jumpToRegister(eventId);
  };

  const backdrop = $("modal-backdrop");
  backdrop.hidden = false;
  requestAnimationFrame(() => backdrop.classList.add("is-open"));
  $("modal-close").focus();
}

function closeModal() {
  const backdrop = $("modal-backdrop");
  backdrop.classList.remove("is-open");
  setTimeout(() => { backdrop.hidden = true; }, 200);
  if (lastFocusedBeforeModal) lastFocusedBeforeModal.focus();
}

/* --------------------------------------------------------------------
   8.5. My Tickets — GET /registrations/{email} and DELETE /registration/{id}
   -------------------------------------------------------------------- */

function showLookupError(message) {
  const el = $("lookup-error");
  if (!message) {
    el.hidden = true;
    el.textContent = "";
    return;
  }
  el.hidden = false;
  el.textContent = message;
}

async function handleLookupSubmit(e) {
  e.preventDefault();
  showLookupError("");

  const email = $("lookup-email").value.trim().toLowerCase();
  if (!email) return showLookupError("Please enter your email address.");
  if (!EMAIL_RE.test(email)) return showLookupError("Please enter a valid email address.");

  const btn = $("lookup-btn");
  btn.disabled = true;
  btn.classList.add("is-loading");
  $("tickets-results").innerHTML = "";

  try {
    const data = await api(`/registrations/${encodeURIComponent(email)}`);
    renderTicketResults(data.registrations || [], email);
  } catch (err) {
    showLookupError(err.message);
  } finally {
    btn.disabled = false;
    btn.classList.remove("is-loading");
  }
}

function renderTicketResults(registrations, email) {
  const container = $("tickets-results");
  if (!registrations.length) {
    container.innerHTML = `<p class="section-sub">No registrations found for ${escapeHtml(email)}.</p>`;
    return;
  }
  container.innerHTML = "";
  registrations.forEach((reg) => container.appendChild(ticketResultCard(reg)));
}

function ticketResultCard(reg) {
  const ev = allEvents.find((e) => e.eventId === reg.eventId);
  const wrap = document.createElement("div");
  wrap.className = "ticket-result";
  wrap.innerHTML = `
    <div class="boarding-pass">
      <div class="pass-main">
        <p class="eyebrow">${reg.status === "confirmed" ? "Confirmed" : escapeHtml(reg.status)}</p>
        <h3>${escapeHtml(ev ? ev.name || ev.eventId : reg.eventId)}</h3>
        <dl class="pass-details">
          <div><dt>Attendee</dt><dd>${escapeHtml(reg.name)}</dd></div>
          <div><dt>Email</dt><dd>${escapeHtml(reg.email)}</dd></div>
          <div><dt>Date</dt><dd>${escapeHtml(formatDate(ev ? ev.date : null))}</dd></div>
        </dl>
      </div>
      <div class="pass-perf" aria-hidden="true"></div>
      <div class="pass-stub">
        <p class="stub-label">Reg. ID</p>
        <p class="stub-id">GP-${escapeHtml(reg.registrationId.slice(0, 8).toUpperCase())}</p>
      </div>
    </div>
    <div class="ticket-cancel-row">
      <button type="button" class="btn btn-cancel" data-id="${escapeHtml(reg.registrationId)}">Cancel registration</button>
    </div>
  `;
  wrap.querySelector(".btn-cancel").addEventListener("click", (e) => handleCancel(e.currentTarget, wrap));
  return wrap;
}

async function handleCancel(btn, cardEl) {
  const confirmed = window.confirm("Cancel this registration? This can't be undone.");
  if (!confirmed) return;

  const id = btn.dataset.id;
  btn.disabled = true;
  const originalLabel = btn.textContent;
  btn.textContent = "Cancelling…";

  try {
    await api(`/registration/${encodeURIComponent(id)}`, { method: "DELETE" });
    cardEl.classList.add("is-cancelled");
    btn.textContent = "Cancelled";
    await loadEvents(); // seat counts changed, refresh everywhere that shows them
  } catch (err) {
    btn.disabled = false;
    btn.textContent = originalLabel;
    window.alert(err.message);
  }
}

/* --------------------------------------------------------------------
   9. Scroll-reveal for elements marked .reveal
   -------------------------------------------------------------------- */

function setupRevealObserver() {
  const targets = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window) || !targets.length) {
    targets.forEach((el) => el.classList.add("is-visible"));
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );
  targets.forEach((el) => observer.observe(el));
}

/* --------------------------------------------------------------------
   10. Wire everything up
   -------------------------------------------------------------------- */

document.addEventListener("DOMContentLoaded", () => {
  setupRevealObserver();

  $("registration-form").addEventListener("submit", handleRegisterSubmit);
  $("register-another-btn").addEventListener("click", resetRegistrationFlow);

  $("event-select").addEventListener("change", updatePreview);
  $("full-name").addEventListener("input", updatePreview);

  $("lookup-form").addEventListener("submit", handleLookupSubmit);

  $("modal-close").addEventListener("click", closeModal);
  $("modal-backdrop").addEventListener("click", (e) => {
    if (e.target.id === "modal-backdrop") closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("modal-backdrop").hidden) closeModal();
  });

  loadEvents();
  updatePreview();
});
