#!/usr/bin/env python3
"""
Chat History Tracker - Debug tool to identify duplicate message sources

This module tracks where chat messages are being added from to help debug
the repeated text issue in the Flask app.
"""

import time
import traceback
from typing import List, Dict, Any
from collections import defaultdict

class ChatHistoryTracker:
    """Tracks chat message additions to identify duplicates and sources"""
    
    def __init__(self):
        self.call_stack: List[Dict[str, Any]] = []
        self.message_sources: Dict[str, str] = {}
        self.duplicate_count = 0
        self.enabled = True
    
    def track_message_addition(self, role: str, content: str, source_location: str = None):
        """
        Track where messages are being added from
        
        Args:
            role: Message role (user/assistant)
            content: Message content
            source_location: Source file and line (auto-detected if None)
        """
        if not self.enabled:
            return
            
        # Auto-detect source location if not provided
        if source_location is None:
            frame = traceback.extract_stack()[-2]  # Caller frame
            source_location = f"{frame.filename.split('/')[-1]}:{frame.lineno}"
        
        # Create call info
        call_info = {
            'timestamp': time.time(),
            'role': role,
            'content_preview': content[:100] + ('...' if len(content) > 100 else ''),
            'content_length': len(content),
            'source': source_location,
            'full_content_hash': hash(content)
        }
        
        self.call_stack.append(call_info)
        
        # Check for potential duplicates
        message_key = f"{role}:{content}"
        content_hash = hash(content)
        
        if message_key in self.message_sources:
            self.duplicate_count += 1
            print(f"🚨 POTENTIAL DUPLICATE #{self.duplicate_count}")
            print(f"   Content: {content[:50]}...")
            print(f"   Previous source: {self.message_sources[message_key]}")
            print(f"   Current source: {source_location}")
            print(f"   Time since last: {time.time() - self._get_last_message_time(content_hash):.2f}s")
            print()
        
        self.message_sources[message_key] = source_location
    
    def _get_last_message_time(self, content_hash: int) -> float:
        """Get timestamp of last message with same content hash"""
        for call_info in reversed(self.call_stack[:-1]):  # Exclude current message
            if call_info['full_content_hash'] == content_hash:
                return call_info['timestamp']
        return 0
    
    def get_duplicate_summary(self) -> Dict[str, Any]:
        """Get summary of duplicate messages"""
        content_counts = defaultdict(list)
        
        for call_info in self.call_stack:
            content_key = call_info['content_preview']
            content_counts[content_key].append(call_info)
        
        duplicates = {
            content: calls 
            for content, calls in content_counts.items() 
            if len(calls) > 1
        }
        
        return {
            'total_messages': len(self.call_stack),
            'duplicate_groups': len(duplicates),
            'total_duplicates': self.duplicate_count,
            'duplicate_details': duplicates
        }
    
    def print_summary(self):
        """Print a summary of tracked messages and duplicates"""
        summary = self.get_duplicate_summary()
        
        print("=" * 60)
        print("CHAT HISTORY TRACKER SUMMARY")
        print("=" * 60)
        print(f"Total messages tracked: {summary['total_messages']}")
        print(f"Duplicate groups found: {summary['duplicate_groups']}")
        print(f"Total duplicate instances: {summary['total_duplicates']}")
        print()
        
        if summary['duplicate_details']:
            print("DUPLICATE MESSAGE DETAILS:")
            print("-" * 40)
            for content, calls in summary['duplicate_details'].items():
                print(f"Message: {content}")
                print(f"Occurrences: {len(calls)}")
                for i, call in enumerate(calls):
                    print(f"  {i+1}. {call['source']} at {time.ctime(call['timestamp'])}")
                print()
        else:
            print("✅ No duplicates detected!")
    
    def reset(self):
        """Reset the tracker"""
        self.call_stack.clear()
        self.message_sources.clear()
        self.duplicate_count = 0
    
    def enable(self):
        """Enable tracking"""
        self.enabled = True
    
    def disable(self):
        """Disable tracking"""
        self.enabled = False

# Global tracker instance
chat_tracker = ChatHistoryTracker()

def track_chat_message(role: str, content: str):
    """Convenience function to track a chat message"""
    frame = traceback.extract_stack()[-2]  # Caller frame
    source_location = f"{frame.filename.split('/')[-1]}:{frame.lineno}"
    chat_tracker.track_message_addition(role, content, source_location) 