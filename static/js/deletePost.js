function deletePost(postId) {
    fetch(`/delete_post/${postId}`, { method: 'POST' })
      .then((response) => {
        if (response.ok) {
          const postElement = document.querySelector(`.post[data-post-id="${postId}"]`);
          if (postElement) {
            postElement.remove();
          }
        } else {
          console.error('Error deleting post:', response);
        }
      })
      .catch((error) => {
        console.error('Error deleting post:', error);
      });
  }