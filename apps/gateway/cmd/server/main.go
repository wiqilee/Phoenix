// Phoenix API Gateway
//
// The gateway is the front door to Phoenix. It receives webhooks from GitLab,
// authenticates them, forwards them to the Python ADK agent service, and
// streams live agent activity to the dashboard over WebSocket.
//
// The gateway does NOT do reasoning. All reasoning happens in the Python
// agent service which runs on the Google ADK. The gateway is pure transport.

package main

import (
	"fmt"
	"os"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"
	"github.com/joho/godotenv"
	"github.com/rs/zerolog"
	zlog "github.com/rs/zerolog/log"

	"github.com/wiqi-lee/phoenix/gateway/internal/routes"
	"github.com/wiqi-lee/phoenix/gateway/internal/websocket"
)

func main() {
	_ = godotenv.Load()
	zerolog.TimeFieldFormat = zerolog.TimeFormatUnix

	port := getEnv("GATEWAY_PORT", "8080")
	agentURL := getEnv("AGENT_URL", "http://agent:8000")

	zlog.Info().
		Str("port", port).
		Str("agent_url", agentURL).
		Msg("phoenix.gateway.starting")

	app := fiber.New(fiber.Config{
		AppName:               "Phoenix Gateway",
		DisableStartupMessage: false,
		ServerHeader:          "phoenix-gateway",
	})

	// Middleware
	app.Use(recover.New())
	app.Use(logger.New(logger.Config{
		Format: "[${time}] ${status} ${method} ${path} (${latency})\n",
	}))
	app.Use(cors.New(cors.Config{
		AllowOrigins: "*",
		AllowMethods: "GET,POST,PUT,DELETE,OPTIONS",
		AllowHeaders: "Origin,Content-Type,Accept,Authorization,X-Gitlab-Token",
	}))

	// Initialize WebSocket hub
	hub := websocket.NewHub()
	go hub.Run()

	// Register routes
	routes.Register(app, agentURL, hub)

	// Health and root
	app.Get("/", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{
			"service": "phoenix-gateway",
			"version": "0.1.0",
			"author":  "Wiqi Lee",
		})
	})

	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{
			"status": "healthy",
		})
	})

	// Start server
	if err := app.Listen(":" + port); err != nil {
		zlog.Fatal().Err(err).Msg("phoenix.gateway.failed_to_start")
	}
}

func getEnv(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}

// Ensure we don't import unused packages in slim build
var _ = fmt.Sprintf
