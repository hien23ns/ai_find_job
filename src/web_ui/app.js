// Front-end Application Logic for ai-find-job Desktop Web Application
let csrfToken = "";
let currentSelectedJobId = null;
let currentApplicationId = null;
let currentQuestionAppId = null;
let currentQuestionFieldId = null;

// Initialize on load
document.addEventListener("DOMContentLoaded", async () => {
  await initCsrf();
  setupNavigation();
  setupEventHandlers();
  loadDashboardData();
  startQueuePolling();
});

async function initCsrf() {
  try {
    const res = await fetch("/api/csrf-token");
    const data = await res.json();
    csrfToken = data.csrf_token;
  } catch (e) {
    console.error("Failed to fetch CSRF token", e);
  }
}

function getFetchHeaders(includeJson = true) {
  const headers = {
    "X-CSRF-Token": csrfToken
  };
  if (includeJson) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerText = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

// Navigation Tab Router
function setupNavigation() {
  const navLinks = document.querySelectorAll(".nav-link");
  navLinks.forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const tab = link.getAttribute("data-tab");
      navToTab(tab);
    });
  });
}

function navToTab(tabName) {
  document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
  document.querySelectorAll(".page-section").forEach(s => s.classList.remove("active"));

  const targetLink = document.querySelector(`.nav-link[data-tab='${tabName}']`);
  const targetSec = document.getElementById(`sec-${tabName}`);

  if (targetLink) targetLink.classList.add("active");
  if (targetSec) targetSec.classList.add("active");

  const titles = {
    dashboard: "Tổng quan hệ thống",
    profile: "Hồ sơ cá nhân ứng viên",
    search: "Tìm kiếm & Lọc việc làm",
    packages: "Bộ hồ sơ & Soạn thảo",
    queue: "Trung tâm ứng tuyển tự động",
    tracker: "Theo dõi đơn ứng tuyển (Tracker)",
    settings: "Cài đặt & Tự động hóa"
  };
  document.getElementById("page-header-title").innerText = titles[tabName] || "Hệ thống";

  // Tab-specific loaders
  if (tabName === "dashboard") loadDashboardData();
  if (tabName === "profile") loadProfileData();
  if (tabName === "search") loadJobsList();
  if (tabName === "packages") {
    if (currentSelectedJobId) {
      loadPackageDetails(currentSelectedJobId);
    } else {
      loadLatestPackage();
    }
  }
  if (tabName === "queue") loadQueueData();
  if (tabName === "tracker") loadTrackerData();
  if (tabName === "settings") loadSettingsData();
}

function openPackageTabForJob(jobId) {
  currentSelectedJobId = jobId;
  navToTab("packages");
  loadPackageDetails(jobId);
}

async function loadLatestPackage() {
  try {
    const res = await fetch("/api/queue");
    const apps = await res.json();
    if (apps && apps.length > 0) {
      const readyApp = apps.find(a => a.package_dir) || apps[0];
      currentSelectedJobId = readyApp.job_id;
      loadPackageDetails(readyApp.job_id);
    } else {
      const jobsRes = await fetch("/api/jobs");
      const jobs = await jobsRes.json();
      if (jobs && jobs.length > 0) {
        currentSelectedJobId = jobs[0].id;
        loadPackageDetails(jobs[0].id);
      }
    }
  } catch (e) {
    console.error("Error loading latest package", e);
  }
}

// Setup Event Handlers
function setupEventHandlers() {
  document.getElementById("kill-switch-btn").addEventListener("click", triggerKillSwitch);
  document.getElementById("btn-save-profile").addEventListener("click", saveProfileData);
  document.getElementById("btn-run-search").addEventListener("click", runJobSearch);
  document.getElementById("btn-save-doc-edits").addEventListener("click", savePackageEdits);
  document.getElementById("btn-save-settings").addEventListener("click", saveSettingsData);
  document.getElementById("btn-test-browser-connection").addEventListener("click", testBrowserConnection);
  document.getElementById("btn-test-email-connection").addEventListener("click", testEmailConnection);
  document.getElementById("btn-submit-q-answer").addEventListener("click", submitQuestionAnswer);
  document.getElementById("btn-modal-create-pkg").addEventListener("click", createPackageForCurrentJob);

  const btnForm = document.getElementById("btn-trigger-form-fill");
  if (btnForm) btnForm.addEventListener("click", triggerDirectFormFill);
  const btnEmail = document.getElementById("btn-trigger-send-email");
  if (btnEmail) btnEmail.addEventListener("click", triggerDirectSendEmail);
  const btnQueue = document.getElementById("btn-enqueue-app");
  if (btnQueue) btnQueue.addEventListener("click", enqueueCurrentPackage);

  const btnAutoApplyDirect = document.getElementById("btn-auto-apply-email-direct");
  if (btnAutoApplyDirect) btnAutoApplyDirect.addEventListener("click", () => {
    triggerAutoApplyEmail(currentSelectedJobId || currentApplicationId);
  });
  const btnModalAutoApply = document.getElementById("btn-modal-auto-apply");
  if (btnModalAutoApply) btnModalAutoApply.addEventListener("click", () => {
    triggerAutoApplyEmail(currentSelectedJobId);
  });

  const btnSaveGmail = document.getElementById("btn-save-gmail-creds");
  if (btnSaveGmail) btnSaveGmail.addEventListener("click", saveGmailSettings);
  const btnTogglePwd = document.getElementById("btn-toggle-gmail-pwd");
  if (btnTogglePwd) btnTogglePwd.addEventListener("click", toggleGmailPwd);

  const selProvider = document.getElementById("cfg-email-provider-type");
  if (selProvider) {
    selProvider.addEventListener("change", (e) => {
      const container = document.getElementById("cfg-gmail-creds-container");
      if (container) {
        container.style.display = e.target.value === "mock" ? "none" : "block";
      }
    });
  }
}

// 1. Dashboard
async function loadDashboardData() {
  try {
    const res = await fetch("/api/dashboard");
    const data = await res.json();
    const s = data.summary;

    document.getElementById("kpi-total-jobs").innerText = s.total_jobs;
    document.getElementById("kpi-submitted-jobs").innerText = s.submitted_jobs;
    document.getElementById("kpi-attention-jobs").innerText = s.needs_attention;
    document.getElementById("kpi-queue-count").innerText = s.queue_count;

    document.getElementById("text-worker").innerText = `Worker: ${data.worker_status}`;
    document.getElementById("text-browser").innerText = `Browser: ${data.browser_status}`;
    document.getElementById("text-email").innerText = `Email: ${data.email_status}`;

    // Load recent matching jobs
    const jobsRes = await fetch("/api/jobs");
    const jobs = await jobsRes.json();
    const tbody = document.querySelector("#dashboard-recent-jobs-table tbody");
    jobs.slice(0, 6).forEach(j => {
      const tr = document.createElement("tr");
      const actionBtn = j.has_hr_email
        ? `<button class="btn btn-success btn-sm" style="background:#15803d; color:#fff; font-weight:700; margin-left:4px;" onclick="triggerAutoApplyEmail('${j.id}')">🚀 Apply Mail</button>`
        : `<button class="btn btn-primary btn-sm" style="background:#2563eb; color:#fff; font-weight:700; margin-left:4px;" onclick="openFormHelperModal('${j.id}')">📝 Mở Form</button>`;

      const channelBadge = j.has_hr_email
        ? `<span class="badge badge-green" style="font-size:11px;">✉️ ${escapeHtml(j.hr_email)}</span>`
        : `<span class="badge badge-amber" style="font-size:11px;">🌐 Nộp Form</span>`;

      tr.innerHTML = `
        <td style="font-weight:600;">${escapeHtml(j.company)}</td>
        <td>${escapeHtml(j.title)}</td>
        <td>${channelBadge}</td>
        <td><span class="badge ${j.match_score >= 80 ? 'badge-green' : 'badge-amber'}">${j.match_score}/100</span></td>
        <td><span class="badge ${getStatusBadgeClass(j.status)}">${escapeHtml(j.status)}</span></td>
        <td style="white-space:nowrap;">
          <button class="btn btn-secondary btn-sm" onclick="openJobDetail('${j.id}')">Chi tiết</button>
          ${actionBtn}
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error("Error loading dashboard", e);
  }
}

// 2. Profile
async function loadProfileData() {
  try {
    const res = await fetch("/api/profile");
    const data = await res.json();

    // Basic & Contact
    document.getElementById("prof-name").value = data.name || "";
    document.getElementById("prof-email").value = data.contact?.email || "";
    document.getElementById("prof-phone").value = data.contact?.phone || "";
    document.getElementById("prof-location").value = data.contact?.location || "Ngũ Hành Sơn, Đà Nẵng, Việt Nam";

    const links = [];
    if (data.contact?.github) links.push(`GitHub: ${data.contact.github}`);
    if (data.contact?.linkedin) links.push(`LinkedIn: ${data.contact.linkedin}`);
    if (data.contact?.website) links.push(`Web: ${data.contact.website}`);
    document.getElementById("prof-links").value = links.join(" | ");

    // Education
    const eduList = Array.isArray(data.education) ? data.education : [data.education || {}];
    const edu = eduList[0] || {};
    const major = edu.major || "";
    const inst = edu.institution || edu.university || "";
    document.getElementById("prof-major").value = (major && inst) ? `${major} - ${inst}` : (major || inst || "Mạng và An toàn thông tin - VKU");
    document.getElementById("prof-grad").value = edu.year || "2023 - 2028 (dự kiến tốt nghiệp)";

    // Summary
    document.getElementById("prof-summary").value = data.summary || "";

    // Skills
    let skillsFormatted = "";
    if (data.skills && typeof data.skills === "object") {
      if (Array.isArray(data.skills)) {
        skillsFormatted = data.skills.join(", ");
      } else {
        const catMap = {
          network: "Mạng & Giao thức",
          systems: "Hệ điều hành",
          security: "An ninh mạng",
          programming: "Ngôn ngữ lập trình",
          cloud: "Điện toán đám mây (AWS)"
        };
        const lines = [];
        for (const [cat, arr] of Object.entries(data.skills)) {
          if (Array.isArray(arr) && arr.length > 0) {
            const label = catMap[cat] || cat.toUpperCase();
            lines.push(`• ${label}: ${arr.join(", ")}`);
          }
        }
        skillsFormatted = lines.join("\n");
      }
    }
    document.getElementById("prof-skills").value = skillsFormatted;

    // Projects
    const projs = data.personal_projects || data.projects || [];
    const projsFormatted = projs.map(p => {
      const tech = (p.technologies && p.technologies.length > 0) ? ` [${p.technologies.join(", ")}]` : "";
      return `• ${p.name}${tech}:\n  ${p.description || ""}`;
    }).join("\n\n");
    document.getElementById("prof-projects").value = projsFormatted;

    // Certifications
    const certs = data.certifications || [];
    const certsFormatted = certs.map(c => `• ${c.name} (${c.issuer || "Tổ chức cấp"}, ${c.year || ""})`).join("\n");
    document.getElementById("prof-certifications").value = certsFormatted || "Chưa có chứng chỉ";

    // Languages
    const langs = data.languages || {};
    const langsFormatted = Object.entries(langs).map(([lang, level]) => `• ${lang.toUpperCase()}: ${level}`).join("\n");
    document.getElementById("prof-languages").value = langsFormatted || "Tiếng Việt, Tiếng Anh";

    // Visa & Availability
    const visa = data.residency_and_visa || {};
    const avail = data.work_availability || {};
    const visaLines = [
      `• Quốc tịch: ${visa.nationality || "Việt Nam"} | Cư trú: ${visa.current_residence || "Việt Nam"}`,
      `• Quyền làm việc VN: ${visa.work_permit_vietnam || "Toàn quyền làm việc"}`,
      `• Visa Hàn Quốc: ${visa.visa_sponsorship_notes || "Cần bảo lãnh E-7 / D-10"}`,
      `• Lịch làm: ${avail.schedule || "Bán thời gian / Thực tập linh hoạt"} (${avail.start_date || "Sẵn sàng ngay"})`
    ];
    document.getElementById("prof-visa").value = visaLines.join("\n");

    // Avatar preview
    document.getElementById("profile-avatar-img").src = "/api/profile/avatar";
  } catch (e) {
    showToast("Không thể tải dữ liệu hồ sơ cá nhân", "error");
  }
}

async function saveProfileData() {
  try {
    const res = await fetch("/api/profile");
    const current = await res.json();

    current.name = document.getElementById("prof-name").value.trim();
    if (!current.contact) current.contact = {};
    current.contact.email = document.getElementById("prof-email").value.trim();
    current.contact.phone = document.getElementById("prof-phone").value.trim();
    current.contact.location = document.getElementById("prof-location").value.trim();
    current.summary = document.getElementById("prof-summary").value.trim();

    // Update education Year if modified (omit GPA completely)
    if (Array.isArray(current.education) && current.education.length > 0) {
      delete current.education[0].gpa;
      current.education[0].year = document.getElementById("prof-grad").value.trim();
    }

    const putRes = await fetch("/api/profile", {
      method: "PUT",
      headers: getFetchHeaders(),
      body: jsonStringifySafe(current)
    });
    const result = await putRes.json();
    showToast(result.message || "Đã lưu hồ sơ thành công vào data/candidates/my_profile.json", "success");
  } catch (e) {
    showToast("Lỗi khi lưu hồ sơ cá nhân", "error");
  }
}

// 3. Search & Job Filtering
let cachedJobsList = [];
let currentJobFilter = "all";
let currentFormJobId = null;

function getCategoryBadge(cat) {
  if (!cat) return "";
  const map = {
    design: '<span class="badge badge-design">🎨 Thiết kế</span>',
    marketing: '<span class="badge badge-marketing">📢 Marketing</span>',
    security: '<span class="badge badge-security">🛡️ An ninh mạng</span>',
    it: '<span class="badge badge-it">💻 CNTT & PM</span>',
    sales: '<span class="badge badge-sales">💼 Sales & BD</span>'
  };
  return map[cat] || `<span class="badge badge-gray">${escapeHtml(cat)}</span>`;
}

function getLocationBadge(loc) {
  if (!loc) return "";
  const map = {
    danang: '<span class="badge badge-location">📍 Đà Nẵng</span>',
    hanoi: '<span class="badge badge-location">📍 Hà Nội</span>',
    hcm: '<span class="badge badge-location">📍 TP.HCM</span>',
    cantho: '<span class="badge badge-location">📍 Cần Thơ</span>',
    haiphong: '<span class="badge badge-location">📍 Hải Phòng</span>',
    remote: '<span class="badge badge-remote">🏠 Remote</span>',
    international: '<span class="badge badge-location">🌏 Quốc tế</span>',
    vietnam: '<span class="badge badge-location">📍 Toàn quốc</span>'
  };
  return map[loc] || `<span class="badge badge-location">📍 ${escapeHtml(loc)}</span>`;
}

function getWorkModeBadge(mode) {
  if (!mode) return "";
  const map = {
    remote: '<span class="badge badge-remote">🏠 Remote / WFH</span>',
    hybrid: '<span class="badge badge-it">🔄 Hybrid</span>',
    onsite: '<span class="badge badge-gray">🏢 On-site</span>'
  };
  return map[mode] || "";
}

function getEmploymentTypeBadge(type) {
  if (!type) return "";
  const map = {
    parttime: '<span class="badge badge-parttime">⏳ Part-time</span>',
    fulltime: '<span class="badge badge-fulltime">⏰ Full-time</span>',
    internship: '<span class="badge badge-intern">🎓 Thực tập sinh</span>',
    freelance: '<span class="badge badge-freelance">💼 Freelance</span>'
  };
  return map[type] || "";
}

async function loadJobsList() {
  try {
    const res = await fetch("/api/jobs");
    cachedJobsList = await res.json();
    const countEl = document.getElementById("search-total-count");
    if (countEl) countEl.innerText = cachedJobsList.length;
    applyFilters();
  } catch (e) {
    console.error("Error loading jobs list", e);
  }
}

function selectQuickCategory(cat) {
  document.querySelectorAll("#quick-category-pills .category-pill").forEach(p => {
    p.classList.toggle("active", p.getAttribute("data-category") === cat);
  });
  const catSel = document.getElementById("search-category");
  if (catSel) catSel.value = cat;

  // Set helpful keywords placeholder/suggestion if field is empty or generic
  const kwInput = document.getElementById("search-keywords");
  if (kwInput) {
    if (cat === "design") kwInput.value = "UI/UX Graphic Designer";
    else if (cat === "marketing") kwInput.value = "Digital Marketing Content";
    else if (cat === "it") kwInput.value = "Software Developer CNTT";
    else if (cat === "security") kwInput.value = "Cyber Security SOC";
    else if (cat === "sales") kwInput.value = "Sales Business Development";
    else if (cat === "all") kwInput.value = "";
  }
  applyFilters();
}

function onCategorySelectChange() {
  const cat = document.getElementById("search-category")?.value || "all";
  document.querySelectorAll("#quick-category-pills .category-pill").forEach(p => {
    p.classList.toggle("active", p.getAttribute("data-category") === cat);
  });
  applyFilters();
}

function filterJobsList(filterType) {
  currentJobFilter = filterType;
  document.querySelectorAll(".quick-filter-chip").forEach(b => b.classList.remove("active"));
  const activeBtn = document.getElementById(`btn-filter-${filterType}`);
  if (activeBtn) activeBtn.classList.add("active");
  applyFilters();
}

function applyFilters() {
  const catFilter = document.getElementById("search-category")?.value || "all";
  const locFilter = document.getElementById("search-location")?.value || "all";
  const modeFilter = document.getElementById("search-work-mode")?.value || "all";
  const typeFilter = document.getElementById("search-employment-type")?.value || "all";
  const chipFilter = currentJobFilter;

  let filtered = cachedJobsList.filter(j => {
    // 1. Category filter
    if (catFilter !== "all" && j.category && j.category !== catFilter) return false;

    // 2. Location filter
    if (locFilter !== "all") {
      if (locFilter === "remote" && j.work_mode !== "remote" && j.location !== "remote") return false;
      if (locFilter !== "remote" && j.location && j.location !== locFilter) return false;
    }

    // 3. Work Mode filter
    if (modeFilter !== "all" && j.work_mode && j.work_mode !== modeFilter) return false;

    // 4. Employment Type filter
    if (typeFilter !== "all" && j.employment_type && j.employment_type !== typeFilter) return false;

    // 5. Quick Filter Chip
    if (chipFilter === "email" && !j.has_hr_email) return false;
    if (chipFilter === "form" && j.has_hr_email) return false;
    if (chipFilter === "remote" && j.work_mode !== "remote" && j.location !== "remote") return false;
    if (chipFilter === "parttime" && j.employment_type !== "parttime") return false;
    if (chipFilter === "design" && j.category !== "design") return false;
    if (chipFilter === "marketing" && j.category !== "marketing") return false;
    if (chipFilter === "danang" && j.location !== "danang") return false;

    return true;
  });

  const countEl = document.getElementById("search-total-count");
  if (countEl) countEl.innerText = filtered.length;

  renderJobsTable(filtered, "#search-results-table tbody");
}

function renderJobsTable(jobs, selector) {
  const tbody = document.querySelector(selector);
  tbody.innerHTML = "";
  if (!jobs || jobs.length === 0) {
    tbody.innerHTML = "<tr><td colspan='7' style='text-align:center; color:#94a3b8; padding:24px;'>Không tìm thấy việc làm phù hợp với bộ lọc hiện tại. Bấm 'Tìm kiếm việc ngay' để quét tin tuyển dụng thực tế mới nhất.</td></tr>";
    return;
  }
  jobs.forEach(j => {
    const tr = document.createElement("tr");

    const channelBadge = j.has_hr_email
      ? `<span class="badge badge-green" style="background:#dcfce7; color:#15803d; border:1px solid #86efac; font-weight:600; font-size:11.5px;">✉️ ${escapeHtml(j.hr_email)}</span>`
      : `<span class="badge badge-amber" style="background:#fef9c3; color:#854d0e; border:1px solid #fde047; font-weight:600; font-size:11.5px;">🌐 Nộp Form / Link</span>`;

    const applyActionBtn = j.has_hr_email
      ? `<button class="btn btn-success btn-sm" style="background:#15803d; color:#fff; font-weight:700; margin-left:4px;" onclick="triggerAutoApplyEmail('${j.id}')">🚀 Gửi Email</button>`
      : `<button class="btn btn-primary btn-sm" style="background:#2563eb; color:#fff; font-weight:700; margin-left:4px;" onclick="openFormHelperModal('${j.id}')">📝 Nộp Form</button>`;

    const isLiveJob = (j.id && j.id.startsWith("job_live_")) || (j.notes && j.notes.includes("Tin tuyển dụng thực tế"));
    const liveTag = isLiveJob ? `<span class="badge badge-green" style="background:#ecfdf5; color:#047857; border:1px solid #6ee7b7; font-size:10px; margin-left:4px;" title="Tin tuyển dụng thực tế đang mở tuyển trên cổng">🟢 Đang tuyển</span>` : "";

    const catBadge = getCategoryBadge(j.category);
    const locBadge = getLocationBadge(j.location);
    const modeBadge = getWorkModeBadge(j.work_mode);
    const typeBadge = getEmploymentTypeBadge(j.employment_type);

    tr.innerHTML = `
      <td>
        <div style="font-weight:700; color:#0f172a; display:flex; align-items:center; gap:4px; flex-wrap:wrap;">
          ${escapeHtml(j.company)} ${liveTag}
        </div>
        <div style="margin-top:4px;">${locBadge}</div>
      </td>
      <td>
        <div style="font-weight:600; color:#1e293b; margin-bottom:4px;">${escapeHtml(j.title)}</div>
        <div>${catBadge}</div>
      </td>
      <td>
        <div style="display:flex; flex-direction:column; gap:4px; align-items:flex-start;">
          ${modeBadge || '<span class="badge badge-gray">🏢 On-site</span>'}
          ${typeBadge || '<span class="badge badge-intern">🎓 Thực tập sinh</span>'}
        </div>
      </td>
      <td>${channelBadge}</td>
      <td><span class="badge ${j.match_score >= 80 ? 'badge-green' : 'badge-amber'}">${j.match_score}/100</span></td>
      <td><span class="badge ${getStatusBadgeClass(j.status)}">${escapeHtml(j.status)}</span></td>
      <td style="white-space:nowrap;">
        <button class="btn btn-secondary btn-sm" onclick="openJobDetail('${j.id}')">JD</button>
        <button class="btn btn-primary btn-sm" style="margin-left:4px;" onclick="openPackageTabForJob('${j.id}')">Hồ sơ</button>
        ${applyActionBtn}
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function openFormHelperModal(jobId) {
  currentFormJobId = jobId;
  currentSelectedJobId = jobId;
  try {
    const res = await fetch(`/api/jobs/${jobId}`);
    const data = await res.json();
    const j = data.job;

    document.getElementById("form-helper-title").innerText = `Hỗ trợ Điền Form: ${j.company} - ${j.title}`;
    document.getElementById("form-helper-subtitle").innerText = `Thị trường: ${j.market.toUpperCase()} | Điểm phù hợp kỹ năng: ${j.match_score}/100`;

    const formUrl = j.source || data.auto_apply_url || "";
    document.getElementById("form-helper-url-text").innerText = formUrl || "Không có đường dẫn web (Xem chi tiết JD)";
    const openBtn = document.getElementById("btn-open-external-form");
    if (formUrl && formUrl.startsWith("http")) {
      openBtn.href = formUrl;
      openBtn.style.display = "inline-flex";
      // Automatically open the form URL in a new browser tab as requested by the user
      window.open(formUrl, "_blank");
      showToast("🌐 Đang mở trang form tuyển dụng trên trình duyệt trong tab mới...", "info");
    } else {
      openBtn.style.display = "none";
    }

    // Load candidate info
    const assistRes = await fetch("/api/candidate/form-assist");
    if (assistRes.ok) {
      const c = await assistRes.json();
      document.getElementById("copy-val-name").innerText = c.full_name || "Ngô Văn Hiền";
      document.getElementById("copy-val-email").innerText = c.email || "hienngo090800@gmail.com";
      document.getElementById("copy-val-phone").innerText = c.phone || "0393492064";
      document.getElementById("copy-val-location").innerText = c.location || "Ngũ Hành Sơn, Đà Nẵng";
      document.getElementById("copy-val-university").innerText = c.university || "Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU)";
      document.getElementById("copy-val-major").innerText = c.major || "Mạng và An toàn thông tin";
      document.getElementById("copy-val-grad").innerText = c.graduation_year || "2028 (Dự kiến)";
      document.getElementById("copy-val-github").innerText = c.github || "https://github.com/hien23ns";
      document.getElementById("copy-val-linkedin").innerText = c.linkedin || "https://www.linkedin.com/in/ngovanhien";
    }

    // Load package info for CV PDF & Cover letter
    const pkgRes = await fetch(`/api/packages/${jobId}`);
    if (pkgRes.ok) {
      const pkg = await pkgRes.json();
      document.getElementById("form-helper-download-pdf").href = pkg.pdf_url;
      document.getElementById("form-helper-view-pdf").href = pkg.pdf_url;
      document.getElementById("form-helper-cl-text").value = pkg.cover_letter_text || "";
    }

    // Hook submit button
    const markBtn = document.getElementById("btn-form-helper-mark-submitted");
    markBtn.onclick = () => markFormAsSubmitted(jobId);

    // Open modal
    document.getElementById("form-helper-modal").classList.add("open");
  } catch (e) {
    showToast("Lỗi khi tải thông tin hỗ trợ điền form", "error");
  }
}

function closeFormHelperModal() {
  document.getElementById("form-helper-modal").classList.remove("open");
}

function copyFormAssistValue(elementId, labelName) {
  const el = document.getElementById(elementId);
  const text = el.tagName === "TEXTAREA" || el.tagName === "INPUT" ? el.value : el.innerText;
  navigator.clipboard.writeText(text).then(() => {
    showToast(`📋 Đã sao chép ${labelName}: ${text}`, "success");
  }).catch(() => {
    showToast(`Đã chọn ${labelName}: ${text}`, "info");
  });
}

async function markFormAsSubmitted(jobId) {
  const targetId = jobId || currentFormJobId;
  if (!targetId) return;

  const btn = document.getElementById("btn-form-helper-mark-submitted");
  btn.innerText = "⏳ Đang cập nhật...";
  btn.disabled = true;

  try {
    const res = await fetch(`/api/jobs/${targetId}/mark-form-submitted`, {
      method: "POST",
      headers: getFetchHeaders()
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || "Đã ghi nhận nộp form thành công!", "success");
      closeFormHelperModal();
      loadDashboardData();
      loadJobsList();
      loadTrackerData();
    } else {
      showToast(data.detail || "Không thể cập nhật trạng thái", "error");
    }
  } catch (e) {
    showToast("Lỗi kết nối khi cập nhật trạng thái nộp form", "error");
  } finally {
    btn.innerText = "✅ Tôi đã nộp xong (Cập nhật Tracker)";
    btn.disabled = false;
  }
}

async function runJobSearch() {
  const btn = document.getElementById("btn-run-search");
  btn.innerText = "🔍 Đang quét tin thật...";
  btn.disabled = true;

  const keywords = (document.getElementById("search-keywords").value || "").trim();
  const category = document.getElementById("search-category")?.value || "all";
  const location = document.getElementById("search-location")?.value || "all";
  const work_mode = document.getElementById("search-work-mode")?.value || "all";
  const employment_type = document.getElementById("search-employment-type")?.value || "all";
  const market = document.getElementById("search-market")?.value || "vietnam";
  const limit = document.getElementById("search-limit")?.value || "5";

  showToast(`🔍 Đang quét và kiểm tra các vị trí tuyển dụng thực tế...`, "info");

  try {
    const res = await fetch("/api/jobs/search", {
      method: "POST",
      headers: getFetchHeaders(),
      body: jsonStringifySafe({ keywords, category, location, work_mode, employment_type, market, limit })
    });
    const data = await res.json();
    const liveNote = data.is_live ? " [🟢 Tin thật đang mở tuyển]" : "";
    showToast(`🎉 Tìm thấy ${data.total_found} tin tuyển dụng thực tế${liveNote}. Đã lưu ${data.imported_count} việc vào danh sách.`, "success");
    await loadJobsList();
  } catch (e) {
    showToast("Lỗi trong quá trình tìm kiếm việc làm", "error");
  } finally {
    btn.innerHTML = `<svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg> Tìm kiếm việc ngay`;
    btn.disabled = false;
  }
}

// 4. Job Details & Package Creation
async function openJobDetail(jobId) {
  currentSelectedJobId = jobId;
  try {
    const res = await fetch(`/api/jobs/${jobId}`);
    const data = await res.json();
    const j = data.job;

    document.getElementById("job-modal-title").innerText = `${j.company} - ${j.title}`;
    const body = document.getElementById("job-modal-body");

    let hrInfoHtml = "";
    const modalAutoApplyBtn = document.getElementById("btn-modal-auto-apply");
    if (data.auto_hr_email) {
      hrInfoHtml = `
        <div style="background:#f0fdf4; border:1px solid #86efac; padding:10px 14px; border-radius:6px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <strong style="color:#166534; font-size:13px;">📧 Email HR chính thức:</strong>
            <span style="color:#15803d; font-weight:700; font-family:monospace; margin-left:8px;">${escapeHtml(data.auto_hr_email)}</span>
          </div>
          <span class="badge badge-green">Sẵn sàng gửi Gmail</span>
        </div>
      `;
      if (modalAutoApplyBtn) {
        modalAutoApplyBtn.style.display = "inline-block";
        modalAutoApplyBtn.innerText = "🚀 Tự gửi Email Apply ngay";
        modalAutoApplyBtn.onclick = () => triggerAutoApplyEmail(jobId);
      }
    } else {
      hrInfoHtml = `
        <div style="background:#fefce8; border:1px solid #fde047; padding:10px 14px; border-radius:6px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <strong style="color:#854d0e; font-size:13px;">🌐 Phương thức nộp:</strong>
            <span style="color:#a16207; font-weight:600; margin-left:8px;">Link ứng tuyển trực tiếp (JD không có email HR)</span>
          </div>
          <span class="badge badge-amber">Nộp qua Form / Link gốc</span>
        </div>
      `;
      if (modalAutoApplyBtn) {
        modalAutoApplyBtn.style.display = "inline-block";
        modalAutoApplyBtn.innerText = "⚡ Mở Link / Tự điền Form";
        modalAutoApplyBtn.onclick = () => {
          closeJobModal();
          navToTab("packages");
          loadPackageDetails(jobId);
        };
      }
    }

    body.innerHTML = `
      <div style="margin-bottom:12px;">
        <span class="badge ${getStatusBadgeClass(j.status)}" style="font-size:12px;">${escapeHtml(j.status)}</span>
        <span class="badge badge-blue" style="margin-left:6px;">Điểm Match: ${j.match_score}/100</span>
        <span class="badge badge-gray" style="margin-left:6px;">Thị trường: ${escapeHtml(j.market)}</span>
        ${(j.id && j.id.startsWith("job_live_")) || (j.notes && j.notes.includes("Tin tuyển dụng thực tế")) ? '<span class="badge badge-green" style="margin-left:6px; background:#dcfce7; color:#15803d; border:1px solid #86efac;">🟢 Đang mở tuyển thật (Live Active)</span>' : ''}
      </div>
      ${hrInfoHtml}
      <p style="font-size:12.5px; color:#475569; margin-bottom:14px;"><strong>Nguồn tuyển dụng:</strong> <a href="${escapeHtml(j.source)}" target="_blank" style="color:#0284c7;">${escapeHtml(j.source)}</a></p>
      <div class="form-group">
        <label class="form-label">Ghi chú & Đánh giá:</label>
        <p style="font-size:13px; color:#1e293b; background:#f8fafc; padding:10px; border-radius:6px; border:1px solid #e2e8f0;">${escapeHtml(j.notes || "Chưa có ghi chú")}</p>
      </div>
      <div class="form-group">
        <label class="form-label">Nội dung JD gốc:</label>
        <textarea class="form-control" readonly style="height:180px; font-size:12px;">${escapeHtml(j.raw_jd || "Đang cập nhật nội dung chi tiết...")}</textarea>
      </div>
    `;

    document.getElementById("job-detail-modal").classList.add("open");
  } catch (e) {
    showToast("Không thể tải chi tiết công việc", "error");
  }
}

function closeJobModal() {
  document.getElementById("job-detail-modal").classList.remove("open");
}

async function createPackageForCurrentJob() {
  if (!currentSelectedJobId) return;
  const btn = document.getElementById("btn-modal-create-pkg");
  btn.innerText = "Đang tạo hồ sơ...";
  btn.disabled = true;

  try {
    const res = await fetch(`/api/jobs/${currentSelectedJobId}/prepare-package`, {
      method: "POST",
      headers: getFetchHeaders()
    });
    const data = await res.json();
    showToast("Đã tạo trọn bộ hồ sơ Modern Tech thành công!", "success");
    closeJobModal();
    // Open packages tab
    navToTab("packages");
    loadPackageDetails(currentSelectedJobId);
  } catch (e) {
    showToast("Lỗi khi tạo bộ hồ sơ", "error");
  } finally {
    btn.innerText = "Tạo bộ hồ sơ";
    btn.disabled = false;
  }
}

async function loadPackageDetails(jobId) {
  try {
    const res = await fetch(`/api/packages/${jobId}`);
    if (!res.ok) {
      showToast("Đang chuẩn bị bộ hồ sơ Modern Tech cho công việc này...", "info");
      const prepRes = await fetch(`/api/jobs/${jobId}/prepare-package`, { method: "POST", headers: getFetchHeaders() });
      if (!prepRes.ok) {
        showToast("Chưa có hồ sơ được tạo cho công việc này.", "warning");
        return;
      }
      return loadPackageDetails(jobId);
    }
    const data = await res.json();
    const app = data.application;
    currentApplicationId = app.id;
    currentSelectedJobId = app.job_id || jobId;

    document.getElementById("package-view-title").innerText = `Hồ sơ ứng tuyển: ${app.company} - ${app.role} [${app.status}]`;
    document.getElementById("cv-pdf-preview-iframe").src = data.pdf_url;
    document.getElementById("btn-download-pdf").href = data.pdf_url;
    document.getElementById("btn-open-preview-html").href = data.preview_html_url;

    document.getElementById("pkg-cover-letter-text").value = data.cover_letter_text;
    document.getElementById("pkg-email-body-text").value = data.email_body_text;

    const chanEl = document.getElementById("pkg-apply-channel");
    const recipEl = document.getElementById("pkg-apply-recipient");
    const badgeEl = document.getElementById("pkg-auto-detected-badge");

    if (chanEl) chanEl.value = app.channel || (data.auto_hr_email ? "email" : "form");
    if (recipEl) recipEl.value = app.recipient || data.auto_hr_email || data.auto_apply_url || "";

    if (badgeEl) {
      if (data.auto_hr_email) {
        badgeEl.style.display = "inline-block";
        badgeEl.innerText = `📧 HR: ${data.auto_hr_email}`;
      } else if (data.auto_apply_url) {
        badgeEl.style.display = "inline-block";
        badgeEl.innerText = `🌐 Form URL sẵn sàng`;
      } else {
        badgeEl.style.display = "none";
      }
    }
  } catch (e) {
    showToast("Lỗi khi tải chi tiết bộ hồ sơ", "error");
  }
}

async function triggerAutoApplyEmail(jobId) {
  const targetJobId = jobId || currentSelectedJobId;
  if (!targetJobId && currentApplicationId) {
    const btn = document.getElementById("btn-auto-apply-email-direct");
    if (btn) btn.disabled = true;
    showToast("🚀 Đang tự động tìm email HR và gửi hồ sơ ứng tuyển...", "info");
    try {
      const res = await fetch(`/api/applications/${currentApplicationId}/auto-apply-email`, {
        method: "POST",
        headers: getFetchHeaders()
      });
      const data = await res.json();
      if (res.ok) {
        if (data.is_mock) {
          showToast(`⚠️ [CHẾ ĐỘ THỬ NGHIỆM]: Đã tìm email HR (${data.hr_email}) & lưu hồ sơ, NHƯNG CHƯA GỬI THẬT vào Gmail vì chưa cài Mật khẩu ứng dụng trong tab Cài đặt!`, "warning");
        } else {
          showToast(`🚀 [ĐÃ GỬI GMAIL THẬT 100%]: Đã gửi CV tới HR (${data.hr_email})! Bạn hãy mở mục "Thư đã gửi" trong Gmail thực để kiểm tra.`, "success");
        }
        loadDashboardData();
        if (currentSelectedJobId) loadPackageDetails(currentSelectedJobId);
        loadTrackerData();
      } else {
        showToast(data.detail || "Không thể tự động gửi email", "error");
      }
    } catch (e) {
      showToast("Lỗi kết nối khi tự động gửi apply", "error");
    } finally {
      if (btn) btn.disabled = false;
    }
    return;
  }

  if (!targetJobId) {
    showToast("Vui lòng chọn một công việc để tự động apply", "warning");
    return;
  }

  showToast("🚀 Đang tự động tìm kiếm email HR và gửi hồ sơ ứng tuyển...", "info");

  try {
    const res = await fetch(`/api/jobs/${targetJobId}/auto-apply-email`, {
      method: "POST",
      headers: getFetchHeaders()
    });
    const data = await res.json();
    if (res.ok) {
      if (data.is_mock) {
        showToast(`⚠️ [CHẾ ĐỘ THỬ NGHIỆM]: Đã tìm email HR (${data.hr_email}) & lưu hồ sơ, NHƯNG CHƯA GỬI THẬT vào Gmail vì chưa cài Mật khẩu ứng dụng trong tab Cài đặt!`, "warning");
      } else {
        showToast(`🚀 [ĐÃ GỬI GMAIL THẬT 100%]: Đã gửi CV tới HR (${data.hr_email})! Bạn hãy mở mục "Thư đã gửi" trong Gmail thực để kiểm tra.`, "success");
      }
      closeJobModal();
      loadDashboardData();
      if (currentSelectedJobId === targetJobId) {
        loadPackageDetails(targetJobId);
      }
      loadTrackerData();
      loadJobsList();
    } else {
      showToast(data.detail || "Không thể tự động gửi email", "error");
    }
  } catch (e) {
    showToast("Lỗi kết nối khi tự động gửi apply", "error");
  }
}

async function triggerDirectFormFill() {
  if (!currentApplicationId) {
    showToast("Vui lòng mở một bộ hồ sơ trước khi bấm điền form", "warning");
    return;
  }
  const channel = document.getElementById("pkg-apply-channel").value;
  const recipient = document.getElementById("pkg-apply-recipient").value.trim();

  const btn = document.getElementById("btn-trigger-form-fill");
  const oldText = btn.innerText;
  btn.innerText = "⏳ Đang mở Playwright & điền form...";
  btn.disabled = true;

  try {
    showToast("Đang khởi động trình duyệt Playwright và tự động điền form...", "info");
    const res = await fetch(`/api/applications/${currentApplicationId}/direct-fill`, {
      method: "POST",
      headers: getFetchHeaders(),
      body: jsonStringifySafe({ channel: "form", recipient: recipient, dry_run: false })
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || "Điền form thành công!", "success");
      if (currentSelectedJobId) loadPackageDetails(currentSelectedJobId);
      loadDashboardData();
    } else {
      showToast(data.detail || "Lỗi khi tự động điền form", "error");
    }
  } catch (e) {
    showToast("Lỗi kết nối khi gửi lệnh điền form", "error");
  } finally {
    btn.innerText = oldText;
    btn.disabled = false;
  }
}

async function triggerDirectSendEmail() {
  if (!currentApplicationId) {
    showToast("Vui lòng mở một bộ hồ sơ trước khi bấm gửi email", "warning");
    return;
  }
  const recipient = document.getElementById("pkg-apply-recipient").value.trim();

  const btn = document.getElementById("btn-trigger-send-email");
  const oldText = btn.innerText;
  btn.innerText = "⏳ Đang gửi email...";
  btn.disabled = true;

  try {
    showToast(`Đang gửi email ứng tuyển kèm CV tới ${recipient || 'HR'}...`, "info");
    const res = await fetch(`/api/applications/${currentApplicationId}/direct-send-email`, {
      method: "POST",
      headers: getFetchHeaders(),
      body: jsonStringifySafe({ channel: "email", recipient: recipient })
    });
    const data = await res.json();
    if (res.ok) {
      if (data.is_mock) {
        showToast(`⚠️ [CHẾ ĐỘ THỬ NGHIỆM]: Email đã ghi nhận cục bộ, NHƯNG CHƯA GỬI THẬT vào Gmail vì chưa cài Mật khẩu ứng dụng trong tab Cài đặt!`, "warning");
      } else {
        showToast(`🚀 [ĐÃ GỬI GMAIL THẬT 100%]: Đã gửi CV tới ${recipient || 'HR'}! Bạn hãy mở mục "Thư đã gửi" trong Gmail thực để kiểm tra.`, "success");
      }
      if (currentSelectedJobId) loadPackageDetails(currentSelectedJobId);
      loadDashboardData();
    } else {
      showToast(data.detail || "Không thể gửi email ứng tuyển", "error");
    }
  } catch (e) {
    showToast("Lỗi kết nối khi gửi email", "error");
  } finally {
    btn.innerText = oldText;
    btn.disabled = false;
  }
}

async function enqueueCurrentPackage() {
  if (!currentApplicationId) {
    showToast("Vui lòng mở một bộ hồ sơ trước khi đưa vào hàng đợi", "warning");
    return;
  }
  const channel = document.getElementById("pkg-apply-channel").value;
  const recipient = document.getElementById("pkg-apply-recipient").value.trim();

  try {
    await fetch(`/api/applications/${currentApplicationId}/channel`, {
      method: "PUT",
      headers: getFetchHeaders(),
      body: jsonStringifySafe({ channel, recipient })
    });

    const res = await fetch("/api/queue/dispatch", {
      method: "POST",
      headers: getFetchHeaders(),
      body: jsonStringifySafe({ application_id: currentApplicationId, action: "queue" })
    });
    const data = await res.json();
    showToast(data.message || "Đã đưa hồ sơ vào hàng đợi ứng tuyển", "success");
    navToTab("queue");
  } catch (e) {
    showToast("Lỗi khi đưa hồ sơ vào hàng đợi", "error");
  }
}

async function savePackageEdits() {
  if (!currentSelectedJobId) {
    showToast("Chưa chọn hồ sơ nào để lưu", "warning");
    return;
  }
  const clText = document.getElementById("pkg-cover-letter-text").value;
  const emailText = document.getElementById("pkg-email-body-text").value;

  try {
    const res = await fetch(`/api/packages/${currentSelectedJobId}/documents`, {
      method: "PUT",
      headers: getFetchHeaders(),
      body: jsonStringifySafe({ cover_letter_text: clText, email_body_text: emailText })
    });
    const data = await res.json();
    showToast(data.message || "Đã lưu thay đổi hồ sơ", "success");
  } catch (e) {
    showToast("Lỗi khi lưu tài liệu ứng tuyển", "error");
  }
}

// 5. Queue Center
async function loadQueueData() {
  try {
    const res = await fetch("/api/queue");
    const apps = await res.json();
    const tbody = document.querySelector("#queue-table tbody");
    tbody.innerHTML = "";

    if (apps.length === 0) {
      tbody.innerHTML = "<tr><td colspan='6' style='text-align:center; color:#94a3b8; padding:20px;'>Hàng đợi đang trống. Chọn việc làm để tạo hồ sơ và đưa vào hàng đợi.</td></tr>";
      return;
    }

    apps.forEach(a => {
      const tr = document.createElement("tr");
      let actionBtns = "";

      if (a.status === "AWAITING_USER") {
        actionBtns = `<button class="btn btn-primary btn-sm" onclick="openQuestionModal('${a.id}', '${escapeHtml(a.current_step || 'Yêu cầu trả lời')}')">Trả lời</button>`;
      } else if (a.status === "NEEDS_REVIEW" || a.status === "READY" || a.status === "DISCOVERED") {
        if (a.channel === "form") {
          actionBtns = `
            <button class="btn btn-primary btn-sm" style="background:#0284c7;" onclick="runDirectFormFill('${a.id}', '${escapeHtml(a.recipient || '')}')">⚡ Điền Form</button>
            <button class="btn btn-secondary btn-sm" onclick="openPackageTabForJob('${a.job_id}')">Xem Hồ sơ</button>
            <button class="btn btn-secondary btn-sm" onclick="dispatchAction('${a.id}', 'pause')">Tạm dừng</button>
          `;
        } else {
          actionBtns = `
            <button class="btn btn-success btn-sm" style="background:#16a34a; color:#fff;" onclick="runDirectSendEmail('${a.id}', '${escapeHtml(a.recipient || '')}')">✉️ Gửi Email</button>
            <button class="btn btn-secondary btn-sm" onclick="openPackageTabForJob('${a.job_id}')">Xem Hồ sơ</button>
            <button class="btn btn-secondary btn-sm" onclick="dispatchAction('${a.id}', 'pause')">Tạm dừng</button>
          `;
        }
      } else if (a.status === "QUEUED" || a.status === "FILLING" || a.status === "SUBMITTING") {
        actionBtns = `
          <button class="btn btn-secondary btn-sm" onclick="dispatchAction('${a.id}', 'pause')">Tạm dừng</button>
          <button class="btn btn-danger btn-sm" onclick="dispatchAction('${a.id}', 'cancel')">Hủy</button>
        `;
      } else if (a.status === "CANCELLED" || a.status === "FAILED") {
        actionBtns = `
          <button class="btn btn-secondary btn-sm" onclick="dispatchAction('${a.id}', 'queue')">Thử lại</button>
          <button class="btn btn-secondary btn-sm" onclick="openPackageTabForJob('${a.job_id}')">Xem Hồ sơ</button>
        `;
      } else if (a.status === "SUBMITTED") {
        actionBtns = `<span class="badge badge-green">Hoàn tất</span> <button class="btn btn-secondary btn-sm" style="margin-left:6px;" onclick="openPackageTabForJob('${a.job_id}')">Xem Hồ sơ</button>`;
      }

      tr.innerHTML = `
        <td style="font-weight:600;">${escapeHtml(a.company)}</td>
        <td>${escapeHtml(a.role)}</td>
        <td><span class="badge badge-gray">${escapeHtml(a.channel)}</span></td>
        <td><span class="badge ${getStatusBadgeClass(a.status)}">${escapeHtml(a.status)}</span></td>
        <td style="font-size:12px; color:#475569;">${escapeHtml(a.current_step || a.status)}</td>
        <td>${actionBtns}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error("Error loading queue", e);
  }
}

function openPackageTabForJob(jobId) {
  if (!jobId) return;
  currentSelectedJobId = jobId;
  navToTab("packages");
  loadPackageDetails(jobId);
}

async function runDirectFormFill(appId, defaultRecipient = "") {
  showToast("Đang mở trình duyệt Playwright để tự điền form...", "info");
  try {
    const res = await fetch(`/api/applications/${appId}/direct-fill`, {
      method: "POST",
      headers: getFetchHeaders(),
      body: jsonStringifySafe({ channel: "form", recipient: defaultRecipient, dry_run: false })
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || "Điền form thành công!", "success");
      loadQueueData();
      loadDashboardData();
    } else {
      showToast(data.detail || "Lỗi điền form", "error");
    }
  } catch (e) {
    showToast("Lỗi kết nối khi gửi lệnh điền form", "error");
  }
}

async function runDirectSendEmail(appId, defaultRecipient = "") {
  showToast("Đang tự động chuẩn bị và gửi email ứng tuyển...", "info");
  try {
    const res = await fetch(`/api/applications/${appId}/auto-apply-email`, {
      method: "POST",
      headers: getFetchHeaders(),
      body: jsonStringifySafe({ channel: "email", recipient: defaultRecipient })
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || `🚀 Đã gửi email thành công tới ${data.hr_email || defaultRecipient}!`, "success");
      loadQueueData();
      loadDashboardData();
      loadTrackerData();
    } else {
      showToast(data.detail || "Không thể gửi email", "error");
    }
  } catch (e) {
    showToast("Lỗi kết nối khi gửi email", "error");
  }
}

async function dispatchAction(appId, action) {
  try {
    const res = await fetch("/api/queue/dispatch", {
      method: "POST",
      headers: getFetchHeaders(),
      body: jsonStringifySafe({ application_id: appId, action: action })
    });
    const data = await res.json();
    showToast(data.message || `Đã gửi lệnh ${action}`, "info");
    loadQueueData();
  } catch (e) {
    showToast("Lỗi khi điều khiển hàng đợi", "error");
  }
}

function startQueuePolling() {
  setInterval(() => {
    const secQueue = document.getElementById("sec-queue");
    if (secQueue && secQueue.classList.contains("active")) {
      loadQueueData();
    }
  }, 3000);
}

// Interactive Question Modal
function openQuestionModal(appId, promptText) {
  currentQuestionAppId = appId;
  currentQuestionFieldId = "custom_field";
  document.getElementById("q-modal-title").innerText = `Cần người dùng can thiệp (Đơn #${appId})`;
  document.getElementById("q-modal-desc").innerText = promptText;
  document.getElementById("q-modal-input").value = "";
  document.getElementById("question-modal").classList.add("open");
}

function closeQuestionModal() {
  document.getElementById("question-modal").classList.remove("open");
}

async function submitQuestionAnswer() {
  const ans = document.getElementById("q-modal-input").value.trim();
  if (!ans) {
    showToast("Vui lòng nhập câu trả lời của bạn", "warning");
    return;
  }
  try {
    const res = await fetch("/api/user-interaction/answer", {
      method: "POST",
      headers: getFetchHeaders(),
      body: jsonStringifySafe({
        application_id: currentQuestionAppId,
        field_id: currentQuestionFieldId,
        answer: ans
      })
    });
    const data = await res.json();
    showToast(data.message || "Đã lưu câu trả lời và tiếp tục hàng đợi", "success");
    closeQuestionModal();
    loadQueueData();
  } catch (e) {
    showToast("Lỗi khi gửi câu trả lời", "error");
  }
}

// 6. Tracker
async function loadTrackerData() {
  try {
    const res = await fetch("/api/jobs");
    const jobs = await res.json();
    const tbody = document.querySelector("#tracker-full-table tbody");
    tbody.innerHTML = "";

    jobs.forEach(j => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-family:monospace; font-size:11.5px;">${escapeHtml(j.id)}</td>
        <td style="font-weight:600;">${escapeHtml(j.company)}</td>
        <td>${escapeHtml(j.title)}</td>
        <td><span class="badge ${j.match_score >= 80 ? 'badge-green' : 'badge-amber'}">${j.match_score}/100</span></td>
        <td><span class="badge ${getStatusBadgeClass(j.status)}">${escapeHtml(j.status)}</span></td>
        <td>${escapeHtml(j.application_date || "-")}</td>
        <td style="font-size:12px; color:#64748b; max-width:260px;">${escapeHtml(j.notes || "")}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error("Error loading tracker data", e);
  }
}

// 7. Settings
async function loadSettingsData() {
  try {
    const res = await fetch("/api/settings");
    const settings = await res.json();
    if (settings.automation_mode) {
      document.getElementById("set-automation-mode").value = settings.automation_mode;
    }
    if (settings.daily_limit) {
      document.getElementById("set-daily-limit").value = settings.daily_limit;
    }

    const selProv = document.getElementById("cfg-email-provider-type");
    if (selProv) {
      selProv.value = settings.email_provider || "mock";
      const container = document.getElementById("cfg-gmail-creds-container");
      if (container) {
        container.style.display = selProv.value === "mock" ? "none" : "block";
      }
    }

    const emailInp = document.getElementById("cfg-gmail-username");
    if (emailInp && settings.email_username) {
      emailInp.value = settings.email_username;
    }

    const badge = document.getElementById("email-mode-badge");
    if (badge) {
      if (settings.is_mock) {
        badge.className = "badge badge-amber";
        badge.innerText = "Đang ở chế độ Thử nghiệm (Mock Offline)";
      } else {
        badge.className = "badge badge-green";
        badge.innerText = "Đã kết nối Gmail THẬT (Google SMTP)";
      }
    }

    const pkgIndicator = document.getElementById("pkg-mode-indicator");
    if (pkgIndicator) {
      if (settings.is_mock) {
        pkgIndicator.innerHTML = '<span style="color:#d97706; font-weight:600; font-size:11.5px;">[Chế độ Thử nghiệm Cục bộ - Vào Cài đặt để gửi Gmail thật]</span>';
      } else {
        pkgIndicator.innerHTML = `<span style="color:#15803d; font-weight:600; font-size:11.5px;">[Sẵn sàng gửi Gmail THẬT: ${escapeHtml(settings.email_username || '')}]</span>`;
      }
    }
  } catch (e) {
    console.error("Error loading settings", e);
  }
}

async function saveSettingsData() {
  const mode = document.getElementById("set-automation-mode").value;
  const limit = document.getElementById("set-daily-limit").value;
  try {
    const res = await fetch("/api/settings", {
      method: "PUT",
      headers: getFetchHeaders(),
      body: jsonStringifySafe({ automation_mode: mode, daily_limit: limit })
    });
    const data = await res.json();
    showToast(data.message || "Đã lưu cài đặt", "success");
  } catch (e) {
    showToast("Lỗi khi lưu cài đặt", "error");
  }
}

async function saveGmailSettings() {
  const provider = document.getElementById("cfg-email-provider-type").value;
  const username = document.getElementById("cfg-gmail-username").value.trim();
  const password = document.getElementById("cfg-gmail-password").value.trim();

  if (provider === "smtp" && !password) {
    showToast("Vui lòng nhập Mật khẩu ứng dụng Google (16 ký tự)", "warning");
    return;
  }

  const btn = document.getElementById("btn-save-gmail-creds");
  const oldText = btn.innerText;
  btn.innerText = "⏳ Đang kết nối Gmail SMTP...";
  btn.disabled = true;

  try {
    showToast("Đang xác thực kết nối tới máy chủ Google Gmail (smtp.gmail.com:587)...", "info");
    const res = await fetch("/api/settings/email", {
      method: "POST",
      headers: getFetchHeaders(),
      body: jsonStringifySafe({ provider, username, password, host: "smtp.gmail.com", port: 587, use_tls: true })
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || "Xác thực Gmail thành công!", "success");
      document.getElementById("cfg-gmail-password").value = "";
      loadSettingsData();
    } else {
      showToast(data.detail || "Không thể xác thực Gmail", "error");
    }
  } catch (e) {
    showToast("Lỗi kết nối khi lưu cài đặt Gmail", "error");
  } finally {
    btn.innerText = oldText;
    btn.disabled = false;
  }
}

function toggleGmailPwd() {
  const inp = document.getElementById("cfg-gmail-password");
  if (inp) {
    inp.type = inp.type === "password" ? "text" : "password";
  }
}

async function triggerKillSwitch() {
  if (!confirm("BẠN CÓ CHẮC CHẮN MUỐN DỪNG TOÀN BỘ HÀNG ĐỢI ỨNG TUYỂN KHẨN CẤP KHÔNG?")) return;
  try {
    const res = await fetch("/api/queue/stop-all", {
      method: "POST",
      headers: getFetchHeaders()
    });
    const data = await res.json();
    showToast(data.message, "error");
    loadQueueData();
    loadDashboardData();
  } catch (e) {
    showToast("Lỗi khi kích hoạt Kill Switch", "error");
  }
}

async function testBrowserConnection() {
  const btn = document.getElementById("btn-test-browser-connection");
  btn.innerText = "Đang kiểm tra trình duyệt...";
  btn.disabled = true;
  try {
    const res = await fetch("/api/browser/test-connection", {
      method: "POST",
      headers: getFetchHeaders()
    });
    const data = await res.json();
    showToast(data.message, data.success ? "success" : "error");
  } catch (e) {
    showToast("Lỗi kết nối tới trình duyệt", "error");
  } finally {
    btn.innerText = "Kiểm tra Trình duyệt Playwright";
    btn.disabled = false;
  }
}

async function testEmailConnection() {
  const btn = document.getElementById("btn-test-email-connection");
  btn.innerText = "Đang kiểm tra mail server...";
  btn.disabled = true;
  try {
    const res = await fetch("/api/email/test-connection", {
      method: "POST",
      headers: getFetchHeaders()
    });
    const data = await res.json();
    showToast(data.message, data.success ? "success" : "error");
  } catch (e) {
    showToast("Lỗi kiểm tra kết nối email", "error");
  } finally {
    btn.innerText = "Kiểm tra Kết nối Email";
    btn.disabled = false;
  }
}

// Helpers
function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function jsonStringifySafe(obj) {
  return JSON.stringify(obj);
}

function getStatusBadgeClass(status) {
  if (!status) return "badge-gray";
  const s = status.toLowerCase();
  if (s.includes("nộp") || s.includes("submitted") || s.includes("sent")) return "badge-green";
  if (s.includes("chuẩn bị") || s.includes("ready") || s.includes("queued")) return "badge-blue";
  if (s.includes("xác minh") || s.includes("awaiting") || s.includes("review")) return "badge-amber";
  if (s.includes("failed") || s.includes("lỗi") || s.includes("cancel")) return "badge-red";
  return "badge-gray";
}
