'use client'

import { useEffect, useState } from 'react'
import QRCode from 'qrcode'

/** A QR code as an inline SVG, drawn in the browser from OUR OWN url — the
 *  markup comes from the qrcode library, never from user input. */
export function QrCode({ value, size = 240, label }: { value: string; size?: number; label: string }) {
  const [svg, setSvg] = useState<string>('')
  useEffect(() => {
    let live = true
    QRCode.toString(value, { type: 'svg', margin: 1, errorCorrectionLevel: 'M' })
      .then((s) => { if (live) setSvg(s) })
      .catch(() => { if (live) setSvg('') })
    return () => { live = false }
  }, [value])
  return (
    <div role="img" aria-label={label} style={{ width: size, height: size }}
         className="mx-auto bg-white [&>svg]:h-full [&>svg]:w-full"
         dangerouslySetInnerHTML={{ __html: svg }} />
  )
}
