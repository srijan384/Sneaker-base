// Function to Add Item to Cart (Connects to Flask)
function addToCart(name, price, image) {
    fetch('/add_to_cart', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            name: name,
            price: price,
            image: image
        }),
    })
    .then(response => response.json())
    .then(data => {
        // Update the Cart Counter in the Header
        document.querySelector('.icons span').innerText = data.count;
        alert("Added to Cart: " + name);
    })
    .catch((error) => {
        console.error('Error:', error);
    });
}