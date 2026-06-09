// Package websocket implements a simple pub/sub hub for streaming
// Phoenix agent activity to connected dashboards.
package websocket

import (
	"encoding/json"
	"sync"

	"github.com/gofiber/contrib/websocket"
	"github.com/google/uuid"
	"github.com/rs/zerolog/log"
)

// Message is a structured event sent to dashboard clients.
type Message struct {
	Type    string         `json:"type"`
	Payload map[string]any `json:"payload"`
}

// Hub is the central broker for WebSocket clients.
type Hub struct {
	clients    map[string]*Client
	mu         sync.RWMutex
	register   chan *Client
	unregister chan *Client
	broadcast  chan Message
}

func NewHub() *Hub {
	return &Hub{
		clients:    make(map[string]*Client),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		broadcast:  make(chan Message, 100),
	}
}

func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client.ID] = client
			h.mu.Unlock()
			log.Info().Str("client_id", client.ID).Msg("phoenix.ws.client_connected")

		case client := <-h.unregister:
			h.mu.Lock()
			delete(h.clients, client.ID)
			h.mu.Unlock()
			log.Info().Str("client_id", client.ID).Msg("phoenix.ws.client_disconnected")
			close(client.Send)

		case message := <-h.broadcast:
			h.mu.RLock()
			for _, client := range h.clients {
				select {
				case client.Send <- message:
				default:
					// Client's send buffer is full, drop them
					close(client.Send)
					delete(h.clients, client.ID)
				}
			}
			h.mu.RUnlock()
		}
	}
}

// Register adds a client to the hub.
func (h *Hub) Register(c *Client) {
	h.register <- c
}

// Unregister removes a client from the hub.
func (h *Hub) Unregister(c *Client) {
	h.unregister <- c
}

// Broadcast sends a message to every connected client.
func (h *Hub) Broadcast(msg Message) {
	select {
	case h.broadcast <- msg:
	default:
		log.Warn().Msg("phoenix.ws.broadcast_queue_full")
	}
}

// Client represents a single connected dashboard.
type Client struct {
	ID   string
	Hub  *Hub
	Conn *websocket.Conn
	Send chan Message
}

func NewClient(hub *Hub, conn *websocket.Conn) *Client {
	return &Client{
		ID:   uuid.NewString(),
		Hub:  hub,
		Conn: conn,
		Send: make(chan Message, 64),
	}
}

// Listen pumps messages from Send channel to the WebSocket connection.
func (c *Client) Listen() {
	defer c.Conn.Close()

	// Send hello on connect
	hello := Message{
		Type: "hello",
		Payload: map[string]any{
			"client_id": c.ID,
			"message":   "Connected to Phoenix",
		},
	}
	if data, err := json.Marshal(hello); err == nil {
		_ = c.Conn.WriteMessage(websocket.TextMessage, data)
	}

	for msg := range c.Send {
		data, err := json.Marshal(msg)
		if err != nil {
			log.Error().Err(err).Msg("phoenix.ws.marshal_failed")
			continue
		}
		if err := c.Conn.WriteMessage(websocket.TextMessage, data); err != nil {
			log.Error().Err(err).Msg("phoenix.ws.write_failed")
			return
		}
	}
}
