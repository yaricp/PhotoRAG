import React, { useMemo, useState } from 'react'
import { Modal } from './Modal'
import type { AvailableDate } from '@/api/client'

const MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
]

interface Props {
    selectedYear: number | null
    selectedMonth: number | null
    selectedDay: number | null
    availableDates: AvailableDate[]
    onSelect: (year?: number, month?: number, day?: number) => void
}

type Step = 'year' | 'month' | 'day'

export function DateFilterButton({
    selectedYear, selectedMonth, selectedDay, availableDates, onSelect,
}: Props) {
    const [open, setOpen] = useState(false)
    const [step, setStep] = useState<Step>('year')

    const label = selectedYear
        ? selectedMonth
            ? selectedDay
                ? `${selectedYear}/${String(selectedMonth).padStart(2, '0')}/${String(selectedDay).padStart(2, '0')}`
                : `${selectedYear}/${String(selectedMonth).padStart(2, '0')}`
            : String(selectedYear)
        : 'Date'

    const dates = Array.isArray(availableDates) ? availableDates : []

    const uniqueYears = useMemo(
        () => [...new Set(dates.map(d => d.year))].sort((a, b) => b - a),
        [dates]
    )

    const availableMonths = useMemo(
        () => [...new Set(dates
            .filter(d => selectedYear == null || d.year === selectedYear)
            .map(d => d.month)
        )].sort((a, b) => a - b),
        [dates, selectedYear]
    )

    const availableDays = useMemo(
        () => [...new Set(dates
            .filter(d =>
                (selectedYear == null || d.year === selectedYear) &&
                (selectedMonth == null || d.month === selectedMonth)
            )
            .map(d => d.day)
        )].sort((a, b) => a - b),
        [dates, selectedYear, selectedMonth]
    )

    function openModal() {
        setStep('year')
        setOpen(true)
    }

    function handleYearClick(year: number) {
        onSelect(year)
        setOpen(false)
    }

    function handleMonthClick(month: number) {
        onSelect(selectedYear ?? undefined, month)
        setOpen(false)
    }

    function handleDayClick(day: number) {
        onSelect(selectedYear ?? undefined, selectedMonth ?? undefined, day)
        setOpen(false)
    }

    function handleClear() {
        onSelect()
        setOpen(false)
    }

    const titles: Record<Step, string> = {
        year: 'Select Year',
        month: 'Select Month',
        day: 'Select Day',
    }

    return (
        <>
            <button
                className={`filter-btn${selectedYear !== null ? ' filter-btn--active' : ''}`}
                onClick={openModal}
            >
                {label}
            </button>

            <Modal open={open} onClose={() => setOpen(false)} title={titles[step]}>
                <div className="filter-modal__date-nav">
                    {step !== 'year' && (
                        <button
                            className="filter-modal__back"
                            onClick={() => setStep(step === 'day' ? 'month' : 'year')}
                        >
                            ← Back
                        </button>
                    )}
                    {selectedYear !== null && (
                        <button className="filter-modal__clear" onClick={handleClear}>
                            Clear date
                        </button>
                    )}
                </div>

                {step === 'year' && (
                    <div className="filter-modal__list">
                        {uniqueYears.map(year => (
                            <button
                                key={year}
                                className={`filter-modal__item${selectedYear === year ? ' filter-modal__item--active' : ''}`}
                                onClick={() => handleYearClick(year)}
                            >
                                {year}
                            </button>
                        ))}
                        <button
                            className="filter-modal__nav-btn"
                            onClick={() => setStep('month')}
                        >
                            Months →
                        </button>
                    </div>
                )}

                {step === 'month' && (
                    <div className="filter-modal__list">
                        {availableMonths.map(month => (
                            <button
                                key={month}
                                className={`filter-modal__item${selectedMonth === month ? ' filter-modal__item--active' : ''}`}
                                onClick={() => handleMonthClick(month)}
                            >
                                {MONTH_NAMES[month - 1]}
                            </button>
                        ))}
                        <button
                            className="filter-modal__nav-btn"
                            onClick={() => setStep('day')}
                        >
                            Days →
                        </button>
                    </div>
                )}

                {step === 'day' && (
                    <div className="filter-modal__list filter-modal__list--days">
                        {availableDays.map(day => (
                            <button
                                key={day}
                                className={`filter-modal__item${selectedDay === day ? ' filter-modal__item--active' : ''}`}
                                onClick={() => handleDayClick(day)}
                            >
                                {day}
                            </button>
                        ))}
                    </div>
                )}
            </Modal>
        </>
    )
}
