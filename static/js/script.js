function addToCart(name, price, image) {
    console.log("Attempting to add:", name); // Debugging line

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
        console.log("Success:", data);
        alert("Added to Cart: " + name); // Visual confirmation
        
        // Update the cart count number in the header
        let counter = document.querySelector('.icons span');
        if (counter) counter.innerText = data.count;
    })
    .catch((error) => {
        console.error('Error:', error);
        alert("Error adding to cart. Check console.");
    });
}