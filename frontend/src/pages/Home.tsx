import { ITEMS } from '../data'
import { A } from '../router'
import { Plate } from '../components/Plate'
import { Card } from './Catalog'

const itemOf = (id: string) => ITEMS.find(i => i.id === id)!

const SV: [string, string, string][] = [
  ['lucide:utensils-crossed', '#0A6A1B', '#fff'],
  ['lucide:sparkles', '#F2B01E', '#3D2817'],
  ['lucide:bike', '#A71930', '#fff'],
  ['lucide:layout-grid', '#FFFCE0', '#0A6A1B'],
]
const WHY = [
  ['lucide:layers', 'Convenient', 'Meals and home help, ordered in one place.'],
  ['lucide:chef-hat', 'Made with care', 'Prepared by Chef Dami for people, families and events.'],
  ['lucide:clock', 'Reliable', 'A confirmation and clear next step after every order.'],
  ['lucide:heart', 'Personal', 'Message or call us. A real person answers.'],
]

export function Home({ add }: { add: (id: string) => void }) {
  const feat = ITEMS.filter(i => ['jr-chicken', 'semo-egusi', 'fr-chicken', 'beans-egg'].includes(i.id))
  const svcs = ITEMS.filter(i => i.kind === 'service')
  return (
    <>
      <section className="hero">
        <div className="wrap hero-in">
          <h1>Your meals. Your home. Made easier.</h1>
          <p>Dami's Lifestyle Services makes everyday life easier. Order home-style Nigerian meals, or book a chef, cleaner, errand runner or home organizer.</p>
          <div className="cta">
            <A to="/menu" className="btn red lg">Order food <iconify-icon icon="lucide:arrow-right" /></A>
            <A to="/menu?svc" className="btn ghost-l lg">Explore services</A>
          </div>
          <ul className="facts">
            <li>Cooked by Chef Dami</li>
            <li>Delivery or pickup</li>
            <li>Pay by card or transfer</li>
          </ul>
        </div>
      </section>

      <section className="sec tint">
        <div className="wrap">
          <div className="sec-h"><h2>Crave it? Order it.</h2><A to="/menu" className="lnk">View menu</A></div>
          <div className="rings">
            {[['Rice', 'jr-chicken'], ['Beans', 'beans-plantain'], ['Pasta', 'js-chicken'], ['Soups', 'semo-egusi'], ['Catering', 'svc-chef']].map(([c, id]) => (
              <A key={c} to={'/menu?' + c} className="ring">
                <span><Plate item={itemOf(id)} /></span>{c}
              </A>
            ))}
          </div>
        </div>
      </section>

      <section className="sec">
        <div className="wrap">
          <div className="sec-h"><h2>Today's best sellers</h2><A to="/menu" className="lnk">See full menu</A></div>
          <div className="grid4">{feat.map(i => <Card key={i.id} item={i} add={add} />)}</div>
        </div>
      </section>

      <section className="svc-dark" id="services">
        <div className="wrap">
          <h2>More than just food.</h2>
          <p>Let us handle the chores while you focus on what matters.</p>
          <div className="svc-list">
            {svcs.map((s, i) => (
              <A key={s.id} to={'/item/' + s.id} className="svc-row">
                <span className="ico" style={{ background: SV[i][1], color: SV[i][2] }}>
                  <iconify-icon icon={SV[i][0]} />
                </span>
                <div><h3>{s.name}</h3><p>{s.desc}</p></div>
                <iconify-icon icon="lucide:chevron-right" className="chev" />
              </A>
            ))}
          </div>
        </div>
      </section>

      <section className="sec" id="about">
        <div className="wrap why">
          <div>
            <h2>Why people choose Dami's</h2>
            <p className="lead">Dami's started with a chef who wanted to give people back their time. Everything is handled personally, from the first message to the last plate.</p>
          </div>
          <ul>
            {WHY.map(([ic, t, d]) => (
              <li key={t}><span className="wi"><iconify-icon icon={ic} /></span><b>{t}</b>{d}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="wrap cta-pad">
        <div className="cta-panel"><i />
          <h2>Ready to make life easier?</h2>
          <p>Place a food order in a few taps, or tell us what you need done at home.</p>
          <div className="cta">
            <A to="/menu" className="btn brown lg">Order now</A>
            <A to="/menu?svc" className="btn ghost-b lg">Request a service</A>
          </div>
        </div>
      </section>
    </>
  )
}
