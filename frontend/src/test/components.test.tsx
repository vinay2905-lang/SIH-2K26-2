import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  ConsentBadge,
  FindingStatusBadge,
  OutcomeBadge,
  SIMULATED_LABEL,
  SeverityBadge,
  SimulatedTag,
} from '@/components/domain'
import { Meter } from '@/components/ui/Stat'
import { formatDate, formatNumber, formatPercent, humanize, roleLabel } from '@/lib/format'

describe('domain components', () => {
  it('labels simulated verification unmistakably', () => {
    render(<SimulatedTag />)
    expect(screen.getByText(SIMULATED_LABEL)).toBeInTheDocument()
    expect(SIMULATED_LABEL).toBe('SIMULATED — NOT OFFICIAL APAAR VERIFICATION')
  })

  it('pairs severity with a text label, never colour alone', () => {
    render(<SeverityBadge value="high" />)
    expect(screen.getByText('High')).toBeInTheDocument()
  })

  it('maps statuses and outcomes to readable labels', () => {
    render(
      <>
        <FindingStatusBadge status="in_review" />
        <OutcomeBadge outcome="unavailable" />
        <ConsentBadge status={null} />
      </>,
    )
    expect(screen.getByText('In review')).toBeInTheDocument()
    expect(screen.getByText('Provider unavailable')).toBeInTheDocument()
    expect(screen.getByText('Not recorded')).toBeInTheDocument()
  })

  it('exposes meters to assistive technology', () => {
    render(<Meter value={65} max={60} label="Regular seats used" status="exceeded" />)
    const meter = screen.getByRole('meter', { name: 'Regular seats used' })
    expect(meter).toHaveAttribute('aria-valuenow', '65')
    expect(meter).toHaveAttribute('aria-valuemax', '60')
  })
})

describe('formatting', () => {
  it('uses Indian digit grouping', () => {
    expect(formatNumber(1234567)).toBe('12,34,567')
    expect(formatNumber(null)).toBe('—')
  })

  it('formats calendar dates without timezone drift', () => {
    expect(formatDate('2026-08-01')).toBe('1 Aug 2026')
  })

  it('formats percentages and labels', () => {
    expect(formatPercent(82.345)).toBe('82.3%')
    expect(formatPercent(null)).toBe('—')
    expect(humanize('CROSS_INSTITUTION_DUPLICATE')).toBe('Cross institution duplicate')
    expect(roleLabel('central_reviewer')).toBe('Central reviewer')
  })
})
