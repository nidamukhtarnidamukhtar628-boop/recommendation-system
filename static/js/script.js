document.addEventListener('DOMContentLoaded', function () {
    const favForms = document.querySelectorAll('.fav-form');

    favForms.forEach(form => {
        form.addEventListener('submit', function (e) {
            e.preventDefault();

            const button = form.querySelector('.fav-btn');
            const icon = button.querySelector('i');
            const movieId = form.dataset.movieId;
            const movieTitle = form.querySelector('input[name="movie_title"]').value;

            fetch(`/favorite/${movieId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: `movie_title=${encodeURIComponent(movieTitle)}`
            })
            .then(res => res.json())
            .then(data => {
                if (data.favorited) {
                    icon.classList.remove('fa-regular');
                    icon.classList.add('fa-solid');
                    button.classList.add('pop-animate');
                } else {
                    icon.classList.remove('fa-solid');
                    icon.classList.add('fa-regular');
                    button.classList.add('shrink-animate');
                }

                setTimeout(() => {
                    button.classList.remove('pop-animate', 'shrink-animate');
                }, 400);
            });
        });
    });
});