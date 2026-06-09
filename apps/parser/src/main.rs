// Phoenix Log Parser
//
// A small Axum service that tokenizes CI logs and extracts error
// signatures. It runs alongside the Python agent and is called via
// HTTP whenever a log needs structured analysis.

use axum::{routing::post, Json, Router};
use once_cell::sync::Lazy;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::env;
use std::net::SocketAddr;
use tower_http::cors::CorsLayer;
use tracing::info;

#[derive(Deserialize)]
struct ParseRequest {
    log: String,
}

#[derive(Serialize)]
struct ParseResponse {
    signature: String,
    category_hint: String,
    excerpt: String,
    matched_patterns: Vec<String>,
}

// Pre-compiled regex patterns for known errors.
struct Pattern {
    regex: Regex,
    name: &'static str,
    signature: &'static str,
    category: &'static str,
}

static PATTERNS: Lazy<Vec<Pattern>> = Lazy::new(|| {
    vec![
        Pattern {
            regex: Regex::new(r"(?i)ERESOLVE.+could not resolve dependency").unwrap(),
            name: "npm_eresolve",
            signature: "npm_eresolve_peer_dep",
            category: "dependency_conflict",
        },
        Pattern {
            regex: Regex::new(r"(?i)peer dep.+missing").unwrap(),
            name: "npm_peer_missing",
            signature: "npm_peer_dep_missing",
            category: "dependency_conflict",
        },
        Pattern {
            regex: Regex::new(r"(?i)ResolutionImpossible|ERROR: Cannot install").unwrap(),
            name: "pip_resolver_failure",
            signature: "pip_resolver_failure",
            category: "dependency_conflict",
        },
        Pattern {
            regex: Regex::new(r"(?i)\d+ problems? \(\d+ errors?").unwrap(),
            name: "eslint_errors",
            signature: "eslint_lint_errors",
            category: "lint_error",
        },
        Pattern {
            regex: Regex::new(r"(?i)would reformat|prettier").unwrap(),
            name: "prettier_format",
            signature: "prettier_format_issue",
            category: "lint_error",
        },
        Pattern {
            regex: Regex::new(r"(?i)ruff.+error").unwrap(),
            name: "ruff_errors",
            signature: "ruff_lint_errors",
            category: "lint_error",
        },
        Pattern {
            regex: Regex::new(r"(?i)gofmt|go vet").unwrap(),
            name: "go_formatting",
            signature: "go_formatting_issue",
            category: "lint_error",
        },
        Pattern {
            regex: Regex::new(r"(?i)test (?:failed|failures?|errored)").unwrap(),
            name: "test_failure",
            signature: "test_failure_generic",
            category: "flaky_test",
        },
        Pattern {
            regex: Regex::new(r"(?i)variable.+(?:not (?:defined|set)|undefined)").unwrap(),
            name: "env_var_missing",
            signature: "ci_env_var_missing",
            category: "config_error",
        },
        Pattern {
            regex: Regex::new(r"(?i)yaml.+(?:invalid|error|syntax)").unwrap(),
            name: "yaml_error",
            signature: "ci_yaml_invalid",
            category: "config_error",
        },
        Pattern {
            regex: Regex::new(r"(?i)(?:exceeded|exhausted|timeout|out of memory|killed)").unwrap(),
            name: "resource_exhausted",
            signature: "job_resource_exhausted",
            category: "resource_timeout",
        },
    ]
});

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let port: u16 = env::var("PARSER_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8001);

    let app = Router::new()
        .route("/parse", post(parse_handler))
        .route("/health", axum::routing::get(health))
        .layer(CorsLayer::permissive());

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    info!("phoenix.parser.listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn health() -> &'static str {
    "ok"
}

async fn parse_handler(Json(req): Json<ParseRequest>) -> Json<ParseResponse> {
    Json(parse_log(&req.log))
}

fn parse_log(log: &str) -> ParseResponse {
    let mut matched_names = Vec::new();
    let mut best: Option<&Pattern> = None;

    for pattern in PATTERNS.iter() {
        if pattern.regex.is_match(log) {
            matched_names.push(pattern.name.to_string());
            if best.is_none() {
                best = Some(pattern);
            }
        }
    }

    let excerpt = extract_excerpt(log);

    match best {
        Some(p) => ParseResponse {
            signature: p.signature.to_string(),
            category_hint: p.category.to_string(),
            excerpt,
            matched_patterns: matched_names,
        },
        None => ParseResponse {
            signature: "unknown".to_string(),
            category_hint: "unknown".to_string(),
            excerpt,
            matched_patterns: matched_names,
        },
    }
}

fn extract_excerpt(log: &str) -> String {
    const MAX: usize = 4000;
    if log.len() <= MAX {
        return log.to_string();
    }
    // Take the last MAX bytes, aligned to a UTF-8 boundary.
    let start = log.len() - MAX;
    let mut idx = start;
    while idx < log.len() && !log.is_char_boundary(idx) {
        idx += 1;
    }
    log[idx..].to_string()
}
