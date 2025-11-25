import cloudscraper
from bs4 import BeautifulSoup
import re
from datetime import date
from typing import List, Dict, Optional, Tuple

class InetProductMonitor:
    """
    A class to monitor Inet.se product pages for new products and deals.
    
    Automatically logs in, tracks multiple pages, and detects new products.
    """
    
    def __init__(self, email: str, password: str, pages: Optional[Tuple[str, ...]] = None):
        """
        Initialize the monitor and log in to Inet.se
        
        Args:
            email: Account email for login
            password: Account password for login
            pages: Optional tuple of page URLs to monitor
        """
        self.email = email
        self.password = password
        self.login_url = "https://www.inet.se/api/user/login"
        self.scraper = None
        self.pages_to_check = list(pages) if pages else []
        self.products = {}  # Dictionary with product_id as key
        self.current_date = date.today()
        
        # Log in on initialization
        self._login()
    
    def _login(self):
        """Log in to Inet.se and create an authenticated session"""
        payload = {
            "email": self.email,
            "password": self.password,
            "isPersistent": True
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        self.scraper = cloudscraper.create_scraper()
        self.scraper.headers.update(headers)
        
        response = self.scraper.post(self.login_url, json=payload)
        if response.status_code == 200:
            print("✓ Login successful!")
        else:
            raise Exception(f"Login failed! Status code: {response.status_code}, Error: {response.text}")
    
    def add_page(self, url: str):
        """
        Add a page URL to the monitoring list
        
        Args:
            url: The URL of the page to monitor
        """
        if url not in self.pages_to_check:
            self.pages_to_check.append(url)
            print(f"✓ [Monitor] Added page: {url}")
            print(f"   Total pages now tracked: {len(self.pages_to_check)}")
        else:
            print(f"⚠ [Monitor] Page already in list: {url}")
            print(f"   Total pages tracked: {len(self.pages_to_check)}")
    
    def _check_date(self):
        """Check if it's a new day and reset if needed"""
        today = date.today()
        if today > self.current_date:
            print(f"🗓️  [Monitor] Date changed: {self.current_date} -> {today}")
            print(f"   Clearing {len(self.products)} tracked product(s)")
            print(f"   Clearing {len(self.pages_to_check)} tracked page(s)")
            self.products = {}
            self.pages_to_check = []
            # Clear pages daily to prevent accumulating expired campaigns
            # If a campaign is still active, it will be re-posted in today's stream
            self.current_date = today
            print("🔄 [Monitor] Re-authenticating with fresh session...")
            self._login()
            print("✅ [Monitor] Ready for new day - waiting for campaign links...")
    
    def _fetch_page(self, url: str) -> str:
        """Fetch HTML content from a URL"""
        response = self.scraper.get(url)
        response.raise_for_status()
        return response.text
    
    def _extract_product_ids(self, html: str) -> List[str]:
        """
        Quickly extract just the product IDs from the page
        
        Args:
            html: HTML content of the page
            
        Returns:
            List of product IDs found on the page
        """
        soup = BeautifulSoup(html, 'html.parser')
        product_items = soup.find_all('li', {'data-test-id': re.compile(r'search_product_\d+')})
        
        product_ids = []
        for item in product_items:
            product_id = item.get('data-test-id', '').replace('search_product_', '')
            if product_id:
                product_ids.append(product_id)
        
        return product_ids
    
    def _extract_product_ids_alt(self, html: str) -> List[str]:
        """
        Extract product IDs from alternate layout (fallback method)
        
        Args:
            html: HTML content of the page
            
        Returns:
            List of product IDs found on the page
        """
        soup = BeautifulSoup(html, 'html.parser')
        product_ids = []
        
        # Find all li elements with class "lamvqw" (alternate layout)
        product_items = soup.find_all('li', class_='lamvqw')
        
        for item in product_items:
            # Extract product ID from the href link
            link = item.find('a', href=True)
            if link:
                href = link['href']
                # Extract ID from URL like /produkt/1977294/...
                match = re.search(r'/produkt/(\d+)/', href)
                if match:
                    product_ids.append(match.group(1))
        
        return product_ids
    
    def _parse_product(self, item) -> Dict:
        """
        Parse a single product element and extract all information
        
        Args:
            item: BeautifulSoup element representing a product
            
        Returns:
            Dictionary with product information
        """
        product = {}
        
        # Extract product ID from data-test-id
        product_id = item.get('data-test-id', '').replace('search_product_', '')
        product['id'] = product_id
        
        # Extract product name
        name_element = item.find('h3', class_=re.compile(r'h1'))
        product['name'] = name_element.text.strip() if name_element else 'N/A'
        
        # Extract product link
        link_element = item.find('a', href=True)
        product['link'] = f"https://www.inet.se{link_element['href']}" if link_element else 'N/A'
        
        # Extract image URL
        img_element = item.find('img')
        product['image'] = img_element['src'] if img_element else 'N/A'
        
        # Check if sold out using SVG circle color
        svg_element = item.find('svg', fill=True)
        if svg_element:
            fill_color = svg_element.get('fill', '')
            product['sold_out'] = 'red' in fill_color.lower()
        else:
            # Fallback to text-based detection
            sold_out_element = item.find('span', string=re.compile(r'Sluts[åä]ld', re.IGNORECASE))
            product['sold_out'] = sold_out_element is not None
        
        # Extract old price (strikethrough price)
        old_price_element = item.find('s', role='deletion')
        if old_price_element:
            old_price_text = old_price_element.text.strip()
            old_price_clean = re.sub(r'[^\d]', '', old_price_text)
            product['old_price'] = int(old_price_clean) if old_price_clean else None
        else:
            product['old_price'] = None
        
        # Extract new price (discounted price)
        new_price_element = item.find('span', {'data-test-is-discounted-price': 'true'})
        if new_price_element:
            new_price_text = new_price_element.text.strip()
            new_price_clean = re.sub(r'[^\d]', '', new_price_text)
            product['new_price'] = int(new_price_clean) if new_price_clean else None
        else:
            # Try to find any price if no discounted price
            price_spans = item.find_all('span', class_=re.compile(r'b1'))
            if price_spans:
                new_price_text = price_spans[0].text.strip()
                new_price_clean = re.sub(r'[^\d]', '', new_price_text)
                product['new_price'] = int(new_price_clean) if new_price_clean else None
            else:
                product['new_price'] = None
        
        # Calculate discount percentage
        if product['old_price'] and product['new_price']:
            discount = ((product['old_price'] - product['new_price']) / product['old_price']) * 100
            product['discount_percent'] = round(discount, 1)
        else:
            product['discount_percent'] = None
        
        return product
    
    def _parse_product_alt(self, item) -> Dict:
        """
        Parse a single product element from alternate layout
        
        Args:
            item: BeautifulSoup element representing a product (alternate layout)
            
        Returns:
            Dictionary with product information
        """
        product = {}
        
        # Extract product link and ID
        link_element = item.find('a', href=True)
        if link_element:
            href = link_element['href']
            product['link'] = f"https://www.inet.se{href}"
            # Extract ID from URL
            match = re.search(r'/produkt/(\d+)/', href)
            product['id'] = match.group(1) if match else 'N/A'
        else:
            product['link'] = 'N/A'
            product['id'] = 'N/A'
        
        # Extract product name (in div with class "dseywor")
        name_element = item.find('div', class_='dseywor')
        product['name'] = name_element.text.strip() if name_element else 'N/A'
        
        # Extract image URL
        img_element = item.find('img', class_='i1n0jahz')
        product['image'] = img_element['src'] if img_element else 'N/A'
        
        # Check if sold out using SVG circle color
        svg_element = item.find('svg', fill=True)
        if svg_element:
            fill_color = svg_element.get('fill', '')
            product['sold_out'] = 'red' in fill_color.lower()
        else:
            # Fallback to text-based detection
            sold_out_element = item.find('span', string=re.compile(r'Sluts[åä]ld', re.IGNORECASE))
            product['sold_out'] = sold_out_element is not None
        
        # Extract old price (s tag with role="deletion")
        old_price_element = item.find('s', role='deletion')
        if old_price_element:
            old_price_text = old_price_element.text.strip()
            old_price_clean = re.sub(r'[^\d]', '', old_price_text)
            product['old_price'] = int(old_price_clean) if old_price_clean else None
        else:
            product['old_price'] = None
        
        # Extract new price (span with data-test-is-discounted-price="true")
        new_price_element = item.find('span', {'data-test-is-discounted-price': 'true'})
        if new_price_element:
            new_price_text = new_price_element.text.strip()
            new_price_clean = re.sub(r'[^\d]', '', new_price_text)
            product['new_price'] = int(new_price_clean) if new_price_clean else None
        else:
            # Try to find any price span
            price_element = item.find('span', class_=re.compile(r'b1'))
            if price_element:
                new_price_text = price_element.text.strip()
                new_price_clean = re.sub(r'[^\d]', '', new_price_text)
                product['new_price'] = int(new_price_clean) if new_price_clean else None
            else:
                product['new_price'] = None
        
        # Calculate discount percentage
        if product['old_price'] and product['new_price']:
            discount = ((product['old_price'] - product['new_price']) / product['old_price']) * 100
            product['discount_percent'] = round(discount, 1)
        else:
            product['discount_percent'] = None
        
        return product
    
    def check_for_new_products(self) -> Dict[str, Dict]:
        """
        Check all monitored pages for new products
        
        Returns:
            Dictionary with new products only (product_id -> product_info)
        """
        print(f"\n{'='*60}")
        print(f"[Monitor] Starting product check")
        print(f"   Date: {date.today()}")
        print(f"   Pages to check: {len(self.pages_to_check)}")
        print(f"   Products already tracked: {len(self.products)}")
        print(f"{'='*60}")
        
        self._check_date()
        
        if not self.pages_to_check:
            print("⚠ [Monitor] No pages to check. Use add_page() to add URLs.")
            return {}
        
        new_products = {}
        
        for page_url in self.pages_to_check:
            print(f"📄 Checking page: {page_url}")
            
            try:
                html = self._fetch_page(page_url)
                soup = BeautifulSoup(html, 'html.parser')
                
                # First pass: Try primary layout
                product_ids = self._extract_product_ids(html)
                use_alt_layout = False
                
                # If no products found, try alternate layout
                if len(product_ids) == 0:
                    print(f"   No products found with primary layout, trying alternate layout...")
                    product_ids = self._extract_product_ids_alt(html)
                    use_alt_layout = True
                
                print(f"   Found {len(product_ids)} products on page (layout: {'alternate' if use_alt_layout else 'primary'})")
                
                # Filter to only new product IDs
                new_ids = [pid for pid in product_ids if pid not in self.products]
                
                if not new_ids:
                    print(f"   ✓ No new products found")
                    continue
                
                print(f"   🆕 Found {len(new_ids)} new products!")
                
                # Second pass: Parse full details only for new products
                if use_alt_layout:
                    # Use alternate layout parser
                    product_items = soup.find_all('li', class_='lamvqw')
                    for item in product_items:
                        link = item.find('a', href=True)
                        if link:
                            href = link['href']
                            match = re.search(r'/produkt/(\d+)/', href)
                            if match:
                                product_id = match.group(1)
                                if product_id in new_ids:
                                    product = self._parse_product_alt(item)
                                    self.products[product_id] = product
                                    new_products[product_id] = product
                else:
                    # Use primary layout parser
                    product_items = soup.find_all('li', {'data-test-id': re.compile(r'search_product_\d+')})
                    for item in product_items:
                        product_id = item.get('data-test-id', '').replace('search_product_', '')
                        if product_id in new_ids:
                            product = self._parse_product(item)
                            self.products[product_id] = product
                            new_products[product_id] = product
                        
            except Exception as e:
                print(f"   ❌ Error checking page: {e}")
        
        return new_products
    
    def get_all_products(self) -> Dict[str, Dict]:
        """Get all tracked products"""
        return self.products
    
    def get_product_count(self) -> int:
        """Get the count of tracked products"""
        return len(self.products)
    
    def __repr__(self):
        return f"InetProductMonitor(pages={len(self.pages_to_check)}, products={len(self.products)}, date={self.current_date})"
