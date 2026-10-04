import { useCallback, useEffect, useState } from 'react'
import {
  cancelOrder,
  cancelServiceRequest,
  listOrders,
  listServiceRequests,
  naira,
} from '../api'
import type { OrderResponse, ServiceRequestResponse } from '../api'
import { A } from '../router'
import { useSession } from '../auth'

const CANCELLABLE_ORDER = 'pending'
const CANCELLABLE_REQUEST = ['requested', 'contacted']

export function Requests() {
  const { isAuthenticated, isLoading, login } = useSession()
  const [orders, setOrders] = useState<OrderResponse[]>([])
  const [requests, setRequests] = useState<ServiceRequestResponse[]>([])
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const [orderPage, requestPage] = await Promise.all([
        listOrders(),
        listServiceRequests(),
      ])
      setOrders(orderPage.items)
      setRequests(requestPage.items)
      setError('')
    } catch {
      setError('We could not load your orders and requests.')
    }
  }, [])

  const runCancel = useCallback(
    async (action: () => Promise<unknown>, message: string) => {
      try {
        await action()
        await load()
      } catch {
        setError(message)
      }
    },
    [load],
  )

  useEffect(() => {
    if (isAuthenticated) void load()
  }, [isAuthenticated, load])

  if (isLoading) return <div className="wrap page"><p>Loading…</p></div>
  if (!isAuthenticated)
    return (
      <div className="wrap page empty">
        <p>Sign in to see your orders and service requests.</p>
        <button className="btn" onClick={login}>
          Sign in
        </button>
      </div>
    )

  return (
    <div className="wrap page">
      <h1 className="h2">Your orders &amp; requests</h1>
      {error && <p className="err">{error}</p>}

      <h2 className="sub">Food orders</h2>
      {orders.length === 0 ? (
        <p className="note">No orders yet.</p>
      ) : (
        <div className="lines">
          {orders.map((order) => (
            <div className="line" key={order.id}>
              <div className="line-i">
                <h3>Order #{order.id}</h3>
                <p>
                  {order.status} · {order.fulfillment_type} · {order.fulfillment_date}
                </p>
              </div>
              <strong>{naira(order.total_minor)}</strong>
              {order.status === CANCELLABLE_ORDER && (
                <button
                  className="lnk"
                  onClick={() =>
                    void runCancel(
                      () => cancelOrder(order.id),
                      'That order can no longer be cancelled.',
                    )
                  }
                >
                  Cancel
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <h2 className="sub">Service requests</h2>
      {requests.length === 0 ? (
        <p className="note">No service requests yet.</p>
      ) : (
        <div className="lines">
          {requests.map((request) => (
            <div className="line" key={request.id}>
              <div className="line-i">
                <h3>Request #{request.id}</h3>
                <p>
                  {request.status}
                  {request.preferred_date ? ` · ${request.preferred_date}` : ''}
                </p>
                <p>{request.details}</p>
              </div>
              {CANCELLABLE_REQUEST.includes(request.status) && (
                <button
                  className="lnk"
                  onClick={() =>
                    void runCancel(
                      () => cancelServiceRequest(request.id),
                      'That request can no longer be cancelled.',
                    )
                  }
                >
                  Cancel
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <p className="note c">
        <A to="/menu" className="lnk">
          Order something else
        </A>
      </p>
    </div>
  )
}
