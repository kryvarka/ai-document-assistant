import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  Lock,
  LogOut,
  Mail,
  Shield,
  Sparkles,
  User as UserIcon,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";

import { loginWithCredentials, registerAccount } from "../api/client";
import type { User } from "../types";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeUser: User | null;
  onAuthSuccess: (user: User) => void;
  onLogout: () => void;
}

export function AuthModal({
  isOpen,
  onClose,
  activeUser,
  onAuthSuccess,
  onLogout,
}: AuthModalProps) {
  const [tab, setTab] = useState<"profile" | "login" | "register">(
    activeUser ? "profile" : "login",
  );
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("Member");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      const res = await loginWithCredentials(email, password);
      onAuthSuccess(res.user);
      setTab("profile");
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Invalid email or password");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      const res = await registerAccount({ name, email, password, role });
      onAuthSuccess(res.user);
      setTab("profile");
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create account");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignOut = () => {
    onLogout();
    setTab("login");
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <div className="auth-modal-header">
          <div className="auth-modal-title">
            <Sparkles size={18} style={{ color: "var(--color-accent)" }} />
            <span>{activeUser && tab === "profile" ? "User Profile" : "Account Authentication"}</span>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} title="Close modal">
            <X size={16} />
          </button>
        </div>

        <div className="auth-tabs">
          {activeUser && (
            <button
              type="button"
              className={`auth-tab ${tab === "profile" ? "active" : ""}`}
              onClick={() => {
                setTab("profile");
                setError(null);
              }}
            >
              <UserIcon size={14} />
              <span>Current Profile</span>
            </button>
          )}
          <button
            type="button"
            className={`auth-tab ${tab === "login" ? "active" : ""}`}
            onClick={() => {
              setTab("login");
              setError(null);
            }}
          >
            <Lock size={14} />
            <span>{activeUser ? "Switch User" : "Sign In"}</span>
          </button>
          <button
            type="button"
            className={`auth-tab ${tab === "register" ? "active" : ""}`}
            onClick={() => {
              setTab("register");
              setError(null);
            }}
          >
            <UserPlus size={14} />
            <span>Create Account</span>
          </button>
        </div>

        {error && (
          <div className="auth-error-banner">
            <AlertCircle size={15} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        {activeUser && tab === "profile" && (
          <div className="profile-modal-content">
            <div className="profile-user-card">
              <div className="profile-avatar-large">
                <UserIcon size={28} />
              </div>
              <div className="profile-user-info">
                <div className="profile-user-name">{activeUser.name}</div>
                <div className="profile-user-email">{activeUser.email}</div>
                <div className="profile-badges-row">
                  <span className="profile-role-badge">
                    <Shield size={11} />
                    {activeUser.role}
                  </span>
                  <span className="profile-status-badge">
                    <CheckCircle2 size={11} />
                    Active Session
                  </span>
                </div>
              </div>
            </div>

            <div className="profile-details-grid">
              <div className="profile-detail-item">
                <div className="profile-detail-label">
                  <Users size={12} />
                  <span>Account ID</span>
                </div>
                <div className="profile-detail-value">{activeUser.id}</div>
              </div>
              <div className="profile-detail-item">
                <div className="profile-detail-label">
                  <Calendar size={12} />
                  <span>Member Since</span>
                </div>
                <div className="profile-detail-value">
                  {new Date(activeUser.created_at).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                  })}
                </div>
              </div>
            </div>

            <div className="profile-actions">
              <button
                type="button"
                className="profile-logout-btn"
                onClick={handleSignOut}
              >
                <LogOut size={14} />
                <span>Sign Out of Account</span>
              </button>
            </div>
          </div>
        )}

        {tab === "login" && (
          <form className="auth-form" onSubmit={handleLogin}>
            <div className="form-group">
              <label>Email Address</label>
              <div className="input-icon-wrapper">
                <Mail size={16} className="input-icon" />
                <input
                  type="email"
                  required
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>
            <div className="form-group">
              <label>Password</label>
              <div className="input-icon-wrapper">
                <Lock size={16} className="input-icon" />
                <input
                  type="password"
                  required
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>
            <button type="submit" className="auth-submit-btn" disabled={isLoading}>
              {isLoading ? "Signing in..." : "Sign In"}
            </button>
          </form>
        )}

        {tab === "register" && (
          <form className="auth-form" onSubmit={handleRegister}>
            <div className="form-group">
              <label>Full Name</label>
              <div className="input-icon-wrapper">
                <UserIcon size={16} className="input-icon" />
                <input
                  type="text"
                  required
                  placeholder="e.g. Alex Johnson"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
            </div>
            <div className="form-group">
              <label>Email Address</label>
              <div className="input-icon-wrapper">
                <Mail size={16} className="input-icon" />
                <input
                  type="email"
                  required
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>
            <div className="form-group">
              <label>Password (min 6 characters)</label>
              <div className="input-icon-wrapper">
                <Lock size={16} className="input-icon" />
                <input
                  type="password"
                  required
                  minLength={6}
                  placeholder="Choose a password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>
            <div className="form-group">
              <label>Role / Specialty</label>
              <div className="input-icon-wrapper">
                <input
                  type="text"
                  placeholder="e.g. Researcher, Engineer, Analyst"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  style={{ paddingLeft: "14px" }}
                />
              </div>
            </div>
            <button type="submit" className="auth-submit-btn" disabled={isLoading}>
              {isLoading ? "Creating Account..." : "Create Account & Sign In"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
