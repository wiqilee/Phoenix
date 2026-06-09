// Package webhook handles incoming GitLab webhook events.
package webhook

import (
	"bytes"
	"encoding/json"
	"net/http"
	"os"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/rs/zerolog/log"

	wshub "github.com/wiqi-lee/phoenix/gateway/internal/websocket"
)

// Handler processes GitLab webhook events and forwards relevant ones
// to the Python agent service.
type Handler struct {
	AgentURL string
	Hub      *wshub.Hub
	Secret   string
	Client   *http.Client
}

func NewHandler(agentURL string, hub *wshub.Hub) *Handler {
	return &Handler{
		AgentURL: agentURL,
		Hub:      hub,
		Secret:   os.Getenv("GITLAB_WEBHOOK_SECRET"),
		Client:   &http.Client{Timeout: 30 * time.Second},
	}
}

// PipelineEvent is the subset of GitLab's pipeline webhook payload we care about.
type PipelineEvent struct {
	ObjectKind       string `json:"object_kind"`
	ObjectAttributes struct {
		ID     int    `json:"id"`
		Status string `json:"status"`
		Ref    string `json:"ref"`
		SHA    string `json:"sha"`
	} `json:"object_attributes"`
	Project struct {
		ID                int    `json:"id"`
		PathWithNamespace string `json:"path_with_namespace"`
	} `json:"project"`
	User struct {
		Username string `json:"username"`
	} `json:"user"`
}

// AgentTriggerRequest is the payload sent to the Python agent.
type AgentTriggerRequest struct {
	ProjectID    string `json:"project_id"`
	PipelineID   int    `json:"pipeline_id"`
	CommitSHA    string `json:"commit_sha"`
	Ref          string `json:"ref"`
	TriggeredBy  string `json:"triggered_by"`
}

// Handle is the Fiber handler for POST /webhooks/gitlab.
func (h *Handler) Handle(c *fiber.Ctx) error {
	// Verify webhook secret (GitLab sends it in the X-Gitlab-Token header)
	if h.Secret != "" {
		token := c.Get("X-Gitlab-Token")
		if token != h.Secret {
			log.Warn().Msg("phoenix.gateway.webhook.invalid_token")
			return fiber.NewError(fiber.StatusUnauthorized, "invalid webhook token")
		}
	}

	var event PipelineEvent
	if err := c.BodyParser(&event); err != nil {
		log.Error().Err(err).Msg("phoenix.gateway.webhook.parse_failed")
		return fiber.NewError(fiber.StatusBadRequest, "invalid payload")
	}

	// Only respond to failed pipeline events
	if event.ObjectKind != "pipeline" {
		return c.JSON(fiber.Map{"status": "ignored", "reason": "not a pipeline event"})
	}
	if event.ObjectAttributes.Status != "failed" {
		return c.JSON(fiber.Map{
			"status": "ignored",
			"reason": "pipeline status is " + event.ObjectAttributes.Status,
		})
	}

	log.Info().
		Int("pipeline_id", event.ObjectAttributes.ID).
		Str("project", event.Project.PathWithNamespace).
		Msg("phoenix.gateway.webhook.failed_pipeline_received")

	// Broadcast to dashboard subscribers immediately
	h.Hub.Broadcast(wshub.Message{
		Type: "pipeline_failed",
		Payload: map[string]any{
			"pipeline_id": event.ObjectAttributes.ID,
			"project":     event.Project.PathWithNamespace,
			"ref":         event.ObjectAttributes.Ref,
			"sha":         event.ObjectAttributes.SHA,
			"user":        event.User.Username,
		},
	})

	// Trigger the Python agent
	triggerReq := AgentTriggerRequest{
		ProjectID:   event.Project.PathWithNamespace,
		PipelineID:  event.ObjectAttributes.ID,
		CommitSHA:   event.ObjectAttributes.SHA,
		Ref:         event.ObjectAttributes.Ref,
		TriggeredBy: "gitlab_webhook",
	}

	go h.forwardToAgent(triggerReq)

	return c.Status(fiber.StatusAccepted).JSON(fiber.Map{
		"status":  "accepted",
		"message": "Phoenix agent triggered",
	})
}

func (h *Handler) forwardToAgent(req AgentTriggerRequest) {
	body, err := json.Marshal(req)
	if err != nil {
		log.Error().Err(err).Msg("phoenix.gateway.webhook.marshal_failed")
		return
	}

	resp, err := h.Client.Post(
		h.AgentURL+"/trigger",
		"application/json",
		bytes.NewReader(body),
	)
	if err != nil {
		log.Error().Err(err).Msg("phoenix.gateway.webhook.agent_forward_failed")
		return
	}
	defer resp.Body.Close()

	log.Info().
		Int("status", resp.StatusCode).
		Int("pipeline_id", req.PipelineID).
		Msg("phoenix.gateway.webhook.agent_notified")
}
