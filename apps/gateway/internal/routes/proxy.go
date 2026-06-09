package routes

import (
	"io"
	"net/http"
	"time"

	"github.com/gofiber/fiber/v2"
)

var httpClient = &http.Client{Timeout: 30 * time.Second}

func proxyGetRuns(agentURL string) fiber.Handler {
	return func(c *fiber.Ctx) error {
		limit := c.Query("limit", "20")
		url := agentURL + "/runs?limit=" + limit

		resp, err := httpClient.Get(url)
		if err != nil {
			return fiber.NewError(fiber.StatusBadGateway, "agent unreachable: "+err.Error())
		}
		defer resp.Body.Close()

		body, err := io.ReadAll(resp.Body)
		if err != nil {
			return fiber.NewError(fiber.StatusInternalServerError, err.Error())
		}
		c.Set("Content-Type", "application/json")
		return c.Status(resp.StatusCode).Send(body)
	}
}

func proxyGetRun(agentURL string) fiber.Handler {
	return func(c *fiber.Ctx) error {
		id := c.Params("id")
		resp, err := httpClient.Get(agentURL + "/runs/" + id)
		if err != nil {
			return fiber.NewError(fiber.StatusBadGateway, "agent unreachable: "+err.Error())
		}
		defer resp.Body.Close()

		body, err := io.ReadAll(resp.Body)
		if err != nil {
			return fiber.NewError(fiber.StatusInternalServerError, err.Error())
		}
		c.Set("Content-Type", "application/json")
		return c.Status(resp.StatusCode).Send(body)
	}
}
