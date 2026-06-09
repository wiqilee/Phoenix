// Package routes wires up all HTTP routes for the Phoenix gateway.
package routes

import (
	"github.com/gofiber/contrib/websocket"
	"github.com/gofiber/fiber/v2"

	"github.com/wiqi-lee/phoenix/gateway/internal/webhook"
	wshub "github.com/wiqi-lee/phoenix/gateway/internal/websocket"
)

// Register attaches all Phoenix routes to the Fiber app.
func Register(app *fiber.App, agentURL string, hub *wshub.Hub) {
	// GitLab webhook intake
	webhookHandler := webhook.NewHandler(agentURL, hub)
	app.Post("/webhooks/gitlab", webhookHandler.Handle)

	// Run query endpoints (proxy to the agent)
	app.Get("/api/runs", proxyGetRuns(agentURL))
	app.Get("/api/runs/:id", proxyGetRun(agentURL))

	// WebSocket endpoint for live dashboard updates
	app.Use("/ws", func(c *fiber.Ctx) error {
		if websocket.IsWebSocketUpgrade(c) {
			c.Locals("allowed", true)
			return c.Next()
		}
		return fiber.ErrUpgradeRequired
	})

	app.Get("/ws", websocket.New(func(c *websocket.Conn) {
		client := wshub.NewClient(hub, c)
		hub.Register(client)
		defer hub.Unregister(client)
		client.Listen()
	}))
}
