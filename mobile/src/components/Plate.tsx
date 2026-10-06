import { Image, StyleSheet, View } from 'react-native'
import Svg, { Ellipse, Path } from 'react-native-svg'
import { toneFor } from '../data'
import { C } from '../theme'
import type { CatalogItem } from '../types'

export function Plate({ item }: { item: CatalogItem }) {
  const svc = item.kind === 'service'
  if (item.image_url) {
    return (
      <View style={styles.plate}>
        <Image source={{ uri: item.image_url }} style={styles.img} resizeMode="cover" />
      </View>
    )
  }
  return (
    <View style={[styles.plate, { backgroundColor: svc ? C.green : C.cream2 }]}>
      <Svg viewBox="0 0 200 140" width="100%" height="100%">
        {svc ? (
          <>
            <Path d="M0 100 Q60 20 120 80 T200 40" stroke={C.gold} strokeWidth={5} fill="none" />
            <Path d="M0 130 Q70 60 130 110 T200 80" stroke={C.gold} strokeWidth={5} fill="none" />
          </>
        ) : (
          <>
            <Ellipse cx={100} cy={76} rx={84} ry={52} fill="#fff" />
            <Ellipse cx={100} cy={76} rx={66} ry={40} fill="#F4EFD0" />
            <Ellipse cx={86} cy={72} rx={38} ry={24} fill={toneFor(item.category)} />
            <Ellipse cx={132} cy={80} rx={20} ry={14} fill={C.gold} />
            <Ellipse cx={120} cy={62} rx={12} ry={8} fill={C.green} opacity={0.8} />
          </>
        )}
      </Svg>
    </View>
  )
}

const styles = StyleSheet.create({
  plate: {
    aspectRatio: 10 / 7,
    borderRadius: 12,
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  img: { width: '100%', height: '100%' },
})