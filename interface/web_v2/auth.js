(function () {
  const view = document.body?.dataset?.authView || "";
  const state = {
    resetToken: "",
    confirmToken: "",
  };

  const el = {
    errorBox: document.getElementById("errorBox"),
    successBox: document.getElementById("successBox"),
    statusLine: document.getElementById("statusLine"),
  };

  document.addEventListener("DOMContentLoaded", () => {
    void bootstrapSessionState();

    if (view === "login") {
      initLogin();
      return;
    }
    if (view === "register") {
      initRegister();
      return;
    }
    if (view === "forgot") {
      initForgotPassword();
    }
  });

  async function bootstrapSessionState() {
    try {
      const response = await fetch("/api/auth/session", { credentials: "same-origin" });
      const payload = await response.json().catch(() => ({}));
      if (payload.setup_required) {
        window.location.href = "/setup";
        return;
      }
      if (payload.authenticated) {
        window.location.href = "/";
      }
    } catch (_error) {
      // Leave the auth page usable if the session check fails.
    }
  }

  function initLogin() {
    const form = document.getElementById("loginForm");
    const usernameInput = document.getElementById("username");
    const passwordInput = document.getElementById("password");
    const submitButton = document.getElementById("submitButton");

    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      hideAlerts();

      const username = String(usernameInput?.value || "").trim();
      const password = String(passwordInput?.value || "").trim();
      if (!username || !password) {
        showError("Please enter both username and password.");
        setStatus("Waiting for complete sign-in details");
        return;
      }

      setBusy(submitButton, true, "Opening AURA...");
      setStatus("Checking your sign-in");

      try {
        const response = await fetch("/api/login", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });
        const payload = await response.json().catch(() => ({}));

        if (!response.ok) {
          showError(payload.detail || "I couldn't verify those details.");
          setStatus("Sign-in didn't match");
          return;
        }

        showSuccess(payload.message || "You're in. Opening AURA.");
        setStatus("Opening AURA");
        window.setTimeout(() => {
          window.location.href = "/";
        }, 900);
      } catch (_error) {
        showError("Connection error. Please try again.");
        setStatus("Connection issue");
      } finally {
        setBusy(submitButton, false, "Access AURA");
      }
    });
  }

  function initRegister() {
    const form = document.getElementById("registerForm");
    const submitButton = document.getElementById("submitButton");

    form?.addEventListener("submit", async (event) => {
      console.log("BUTTON CLICKED: Create account");
      event.preventDefault();
      hideAlerts();

      const name = String(document.getElementById("name")?.value || "").trim();
      const username = String(document.getElementById("username")?.value || "").trim();
      const email = String(document.getElementById("email")?.value || "").trim();
      const password = String(document.getElementById("password")?.value || "").trim();
      const confirmPassword = String(document.getElementById("confirmPassword")?.value || "").trim();

      if (!name || !username || !email || !password || !confirmPassword) {
        showError("Please fill in all fields.");
        setStatus("Fill in all fields to continue");
        return;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        showError("Please enter a valid email address.");
        setStatus("Check your email and try again");
        return;
      }
      if (password.length < 8) {
        showError("Password must be at least 8 characters.");
        setStatus("Password too short");
        return;
      }
      if (password !== confirmPassword) {
        showError("Passwords do not match.");
        setStatus("Password mismatch");
        return;
      }

      setBusy(submitButton, true, "Creating account...");
      setStatus("Creating your account");

      try {
        const response = await fetch("/api/register", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, username, email, password }),
        });
        const payload = await response.json().catch(() => ({}));

        if (!response.ok) {
          showError(payload.detail || "Registration failed.");
          setStatus("Account creation failed");
          return;
        }

        showSuccess(payload.message || "Account created. Opening sign in.");
        setStatus("Account created");
        window.setTimeout(() => {
          window.location.href = "/login";
        }, 1300);
      } catch (_error) {
        showError("Connection error. Please try again.");
        setStatus("Connection issue");
      } finally {
        setBusy(submitButton, false, "Create account");
      }
    });
  }

  function initForgotPassword() {
    const requestButton = document.getElementById("requestButton");
    const verifyButton = document.getElementById("verifyButton");
    const confirmButton = document.getElementById("confirmButton");
    const requestStep = document.getElementById("requestStep");
    const verifyStep = document.getElementById("verifyStep");
    const confirmStep = document.getElementById("confirmStep");

    requestButton?.addEventListener("click", async () => {
      console.log("BUTTON CLICKED: Forgot password — Request");
      hideAlerts();
      const identifier = String(document.getElementById("identifier")?.value || "").trim();
      if (!identifier) {
        showError("Enter your username or email first.");
        setStatus("Waiting for identifier");
        return;
      }

      setBusy(requestButton, true, "Preparing code...");
      setStatus("Preparing reset code");

      try {
        const response = await fetch("/api/auth/password-reset/request", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ identifier }),
        });
        const payload = await response.json().catch(() => ({}));

        if (!response.ok || !payload.success) {
          showError(payload.reason || payload.detail || "Could not request a reset code.");
          setStatus("Reset request failed");
          return;
        }

        state.resetToken = payload.reset_token || payload.token || "";
        const parts = [payload.message || "Reset code issued."];
        if (payload.code) {
          parts.push(`Local reset code: ${payload.code}`);
          const codeInput = document.getElementById("resetCode");
          if (codeInput) {
            codeInput.value = payload.code;
          }
        }
        showSuccess(parts.join(" "));
        requestStep.hidden = true;
        verifyStep.hidden = false;
        setStatus("Reset code ready");
      } catch (_error) {
        showError("Connection error. Please try again.");
        setStatus("Reset request failed");
      } finally {
        setBusy(requestButton, false, "Send reset code");
      }
    });

    verifyButton?.addEventListener("click", async () => {
      console.log("BUTTON CLICKED: Forgot password — Verify");
      hideAlerts();
      const code = String(document.getElementById("resetCode")?.value || "").trim();
      if (!state.resetToken || !code) {
        showError("Enter the reset code first.");
        setStatus("Waiting for reset code");
        return;
      }

      setBusy(verifyButton, true, "Checking code...");
      setStatus("Checking reset code");

      try {
        const response = await fetch("/api/auth/password-reset/verify", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reset_token: state.resetToken, code }),
        });
        const payload = await response.json().catch(() => ({}));

        if (!response.ok || !payload.success) {
          showError(payload.reason || payload.detail || "Verification failed.");
          setStatus("Verification failed");
          return;
        }

        state.confirmToken = payload.confirm_token || "";
        showSuccess(payload.message || "Code verified. Choose your new password.");
        verifyStep.hidden = true;
        confirmStep.hidden = false;
        setStatus("Code confirmed");
      } catch (_error) {
        showError("Connection error. Please try again.");
        setStatus("Code check failed");
      } finally {
        setBusy(verifyButton, false, "Verify code");
      }
    });

    confirmButton?.addEventListener("click", async () => {
      console.log("BUTTON CLICKED: Forgot password — Confirm");
      hideAlerts();
      const newPassword = String(document.getElementById("newPassword")?.value || "").trim();
      const confirmPassword = String(document.getElementById("confirmPassword")?.value || "").trim();

      if (!state.resetToken || !state.confirmToken) {
        showError("The reset session is incomplete. Request a new reset code.");
        setStatus("Reset session incomplete");
        return;
      }
      if (!newPassword || !confirmPassword) {
        showError("Fill in both password fields.");
        setStatus("Waiting for new password");
        return;
      }
      if (newPassword.length < 8) {
        showError("Password must be at least 8 characters.");
        setStatus("Password too short");
        return;
      }
      if (newPassword !== confirmPassword) {
        showError("Passwords do not match.");
        setStatus("Password mismatch");
        return;
      }

      setBusy(confirmButton, true, "Updating password...");
      setStatus("Updating password");

      try {
        const response = await fetch("/api/auth/password-reset/confirm", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            reset_token: state.resetToken,
            confirm_token: state.confirmToken,
            new_password: newPassword,
          }),
        });
        const payload = await response.json().catch(() => ({}));

        if (!response.ok || !payload.success) {
          showError(payload.reason || payload.detail || "Password update failed.");
          setStatus("Password update failed");
          return;
        }

        showSuccess(payload.message || payload.reason || "Password updated. Opening sign in.");
        setStatus("Password updated");
        window.setTimeout(() => {
          window.location.href = "/login";
        }, 1100);
      } catch (_error) {
        showError("Connection error. Please try again.");
        setStatus("Connection issue");
      } finally {
        setBusy(confirmButton, false, "Update password");
      }
    });
  }

  function hideAlerts() {
    el.errorBox?.classList.remove("is-visible");
    el.successBox?.classList.remove("is-visible");
    if (el.errorBox) el.errorBox.textContent = "";
    if (el.successBox) el.successBox.textContent = "";
  }

  function showError(message) {
    if (!el.errorBox) return;
    el.errorBox.textContent = message;
    el.errorBox.classList.add("is-visible");
    el.successBox?.classList.remove("is-visible");
  }

  function showSuccess(message) {
    if (!el.successBox) return;
    el.successBox.textContent = message;
    el.successBox.classList.add("is-visible");
    el.errorBox?.classList.remove("is-visible");
  }

  function setStatus(message) {
    if (el.statusLine) {
      el.statusLine.textContent = message;
    }
  }

  function setBusy(button, busy, busyLabel) {
    if (!button) return;
    const idleLabel = button.dataset.idleLabel || button.textContent;
    button.dataset.idleLabel = idleLabel;
    button.classList.toggle("is-busy", busy);
    button.disabled = busy;
    button.textContent = busy ? busyLabel : idleLabel;
  }
})();
