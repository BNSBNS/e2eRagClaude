'use client'
import React, { createContext, useContext, useEffect, useState } from 'react'
import { io, Socket } from 'socket.io-client'

interface WebSocketContextType {
  socket: Socket | null
  isConnected: boolean
}

const WebSocketContext = createContext<WebSocketContextType>({ 
  socket: null, 
  isConnected: false 
})

export const useWebSocket = () => useContext(WebSocketContext)

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [socket, setSocket] = useState<Socket | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    const newSocket = io('ws://localhost:8000', {
      transports: ['websocket']
    })

    newSocket.on('connect', () => {
      console.log('Connected to WebSocket')
      setIsConnected(true)
    })

    newSocket.on('disconnect', () => {
      console.log('Disconnected from WebSocket')
      setIsConnected(false)
    })

    setSocket(newSocket)

    return () => {
      newSocket.close()
    }
  }, [])

  return (
    <WebSocketContext.Provider value={{ socket, isConnected }}>
      {children}
    </WebSocketContext.Provider>
  )
}