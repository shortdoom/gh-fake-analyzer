import asyncio
import aiohttp
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional
import time


class ConcurrentExecutor:
    """Handles concurrent execution of tasks and API requests."""

    def __init__(self, max_workers: int = 5, api_batch_size: int = 5):
        """
        Initialize the executor with specified limits.
        
        Args:
            max_workers: Maximum number of concurrent threads/workers
            api_batch_size: Maximum number of concurrent API requests
        """
        self.max_workers = max_workers
        self.api_batch_size = api_batch_size
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def run_concurrent(self, func: Callable, items: List[Any]) -> List[Any]:
        """
        Run a function concurrently over a list of items.
        
        Args:
            func: Function to execute
            items: List of items to process
            
        Returns:
            List of results from function execution
        """
        try:
            futures = []
            for item in items:
                future = self.executor.submit(func, item)
                futures.append(future)
            
            results = []
            for future in futures:
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logging.error(f"Error in concurrent execution: {e}")
                    results.append(None)
            
            return results
        except Exception as e:
            logging.error(f"Error in run_concurrent: {e}")
            return [None] * len(items)

    def run_api_requests(self, requests: List[Dict], headers: Optional[Dict] = None) -> List[Any]:
        """
        Run API requests concurrently with rate limiting.
        
        Args:
            requests: List of request dictionaries with 'url' and optional 'params'
            headers: Optional headers to include in requests
            
        Returns:
            List of API response data
        """
        try:
            return asyncio.run(self._run_api_requests_async(requests, headers))
        except Exception as e:
            logging.error(f"Error in run_api_requests: {e}")
            return [None] * len(requests)

    async def _run_api_requests_async(self, requests: List[Dict], headers: Optional[Dict] = None) -> List[Any]:
        """
        Internal async method to handle API requests with rate limiting.
        
        Args:
            requests: List of request dictionaries
            headers: Optional headers for requests
            
        Returns:
            List of API response data
        """
        async with aiohttp.ClientSession(headers=headers) as session:
            tasks = []
            results = []
            
            # Process requests in batches
            for i in range(0, len(requests), self.api_batch_size):
                batch = requests[i:i + self.api_batch_size]
                
                # Create tasks for batch
                batch_tasks = []
                for req in batch:
                    task = asyncio.create_task(
                        self._make_api_request(
                            session,
                            req['url'],
                            req.get('params', None)
                        )
                    )
                    batch_tasks.append(task)
                
                # Wait for batch to complete
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                results.extend(batch_results)
                
                # Add delay between batches
                if i + self.api_batch_size < len(requests):
                    await asyncio.sleep(2)  # 2 second delay between batches
            
            return results

    async def _make_api_request(self, session: aiohttp.ClientSession, url: str, params: Optional[Dict] = None) -> Optional[Any]:
        """
        Make a single API request with retry logic.
        
        Args:
            session: aiohttp ClientSession
            url: Request URL
            params: Optional query parameters
            
        Returns:
            API response data or None on failure
        """
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status in [403, 429]:  # Rate limit
                        retry_after = response.headers.get('Retry-After')
                        if retry_after:
                            await asyncio.sleep(int(retry_after))
                        else:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                    else:
                        logging.error(f"Request failed with status {response.status}: {url}")
                        return None
                        
            except aiohttp.ClientError as e:
                logging.error(f"Request error: {e}")
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
                
        logging.error(f"Max retries exceeded for URL: {url}")
        return None 