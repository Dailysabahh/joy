"""
Business Brain - Action Handlers

Implements actual business actions that AI workers can perform:
- Booking appointments
- Checking availability
- Sending notifications
- Updating CRM
- Transferring calls
"""
import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class BookingSystem:
    """
    Handles appointment booking and availability checking.
    
    In production: Integrate with calendaring systems like:
    - Google Calendar API
    - Microsoft Outlook
    - Custom booking system
    - Restaurant reservation systems
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.bookings: Dict[str, list] = {}  # In-memory store for demo
    
    async def check_availability(
        self,
        business_id: str,
        date: str,
        time: str,
        duration: int = 60  # minutes
    ) -> Dict[str, Any]:
        """
        Check if a time slot is available.
        
        Args:
            business_id: Business identifier
            date: Date in YYYY-MM-DD format
            time: Time in HH:MM format
            duration: Appointment duration in minutes
        
        Returns:
            Availability status and alternative slots if unavailable
        """
        logger.info(f"Checking availability for {business_id} on {date} at {time}")
        
        # Get existing bookings
        key = f"{business_id}:{date}"
        existing_bookings = self.bookings.get(key, [])
        
        # Check for conflicts
        requested_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        requested_end = requested_datetime + timedelta(minutes=duration)
        
        for booking in existing_bookings:
            booking_start = datetime.strptime(
                f"{booking['date']} {booking['time']}", 
                "%Y-%m-%d %H:%M"
            )
            booking_end = booking_start + timedelta(minutes=booking['duration'])
            
            # Check for overlap
            if (requested_datetime < booking_end and requested_end > booking_start):
                # Conflict - suggest alternatives
                alternatives = await self._get_alternative_slots(
                    business_id, date, time, duration
                )
                
                return {
                    'available': False,
                    'message': 'This time slot is already booked',
                    'alternatives': alternatives
                }
        
        return {
            'available': True,
            'message': f'Available on {date} at {time}'
        }
    
    async def book_appointment(
        self,
        business_id: str,
        customer_name: str,
        customer_phone: str,
        customer_email: Optional[str],
        date: str,
        time: str,
        service: str,
        duration: int = 60,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Book an appointment.
        
        Returns:
            Confirmation with booking ID
        """
        # First check availability
        availability = await self.check_availability(business_id, date, time, duration)
        
        if not availability['available']:
            return {
                'success': False,
                'message': 'Time slot not available',
                'alternatives': availability.get('alternatives', [])
            }
        
        # Create booking
        booking_id = f"BK{int(datetime.now().timestamp())}"
        
        booking = {
            'booking_id': booking_id,
            'business_id': business_id,
            'customer_name': customer_name,
            'customer_phone': customer_phone,
            'customer_email': customer_email,
            'date': date,
            'time': time,
            'service': service,
            'duration': duration,
            'notes': notes,
            'status': 'confirmed',
            'created_at': datetime.now().isoformat()
        }
        
        # Store booking
        key = f"{business_id}:{date}"
        if key not in self.bookings:
            self.bookings[key] = []
        self.bookings[key].append(booking)
        
        logger.info(f"Booking created: {booking_id}")
        
        # Send confirmation (in production: SMS, email, etc.)
        await self._send_booking_confirmation(booking)
        
        return {
            'success': True,
            'booking_id': booking_id,
            'message': f'Appointment confirmed for {customer_name} on {date} at {time}',
            'details': booking
        }
    
    async def _get_alternative_slots(
        self,
        business_id: str,
        date: str,
        time: str,
        duration: int,
        num_alternatives: int = 3
    ) -> list[Dict[str, str]]:
        """
        Suggest alternative time slots.
        """
        alternatives = []
        base_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        
        # Try next 1-hour increments
        for i in range(1, 6):
            alt_time = base_time + timedelta(hours=i)
            alt_date = alt_time.strftime("%Y-%m-%d")
            alt_time_str = alt_time.strftime("%H:%M")
            
            avail = await self.check_availability(
                business_id, alt_date, alt_time_str, duration
            )
            
            if avail['available']:
                alternatives.append({
                    'date': alt_date,
                    'time': alt_time_str,
                    'display': alt_time.strftime("%A, %B %d at %I:%M %p")
                })
                
                if len(alternatives) >= num_alternatives:
                    break
        
        return alternatives
    
    async def _send_booking_confirmation(self, booking: Dict[str, Any]) -> None:
        """
        Send booking confirmation to customer.
        """
        logger.info(f"Sending confirmation to {booking['customer_phone']}")
        # In production: Integrate with Twilio, SendGrid, etc.
        
    async def cancel_booking(
        self,
        business_id: str,
        booking_id: str
    ) -> Dict[str, Any]:
        """
        Cancel an existing booking.
        """
        # Find and cancel booking
        for key, bookings in self.bookings.items():
            for booking in bookings:
                if booking['booking_id'] == booking_id:
                    booking['status'] = 'cancelled'
                    
                    logger.info(f"Booking cancelled: {booking_id}")
                    
                    return {
                        'success': True,
                        'message': 'Booking cancelled successfully'
                    }
        
        return {
            'success': False,
            'message': 'Booking not found'
        }


class CRMIntegration:
    """
    CRM integration for customer records.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.customers: Dict[str, Dict] = {}  # In-memory for demo
    
    async def get_customer_by_phone(
        self,
        phone: str
    ) -> Optional[Dict[str, Any]]:
        """
        Look up customer by phone number.
        """
        return self.customers.get(phone)
    
    async def create_or_update_customer(
        self,
        phone: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create or update customer record.
        """
        if phone in self.customers:
            customer = self.customers[phone]
            if name:
                customer['name'] = name
            if email:
                customer['email'] = email
            if notes:
                if 'notes' not in customer:
                    customer['notes'] = []
                customer['notes'].append({
                    'text': notes,
                    'timestamp': datetime.now().isoformat()
                })
        else:
            customer = {
                'phone': phone,
                'name': name,
                'email': email,
                'created_at': datetime.now().isoformat(),
                'notes': []
            }
            self.customers[phone] = customer
        
        return customer


class CallTransfer:
    """
    Handle call transfers to human agents.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    async def transfer_to_human(
        self,
        reason: str,
        department: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transfer call to human agent.
        """
        logger.info(f"Transfer request: {reason} -> {department or 'general'}")
        
        # In production: Integrate with phone system
        # Return transfer target
        return {
            'success': True,
            'transfer_to': department or 'general',
            'message': 'Transferring you to a team member now'
        }
