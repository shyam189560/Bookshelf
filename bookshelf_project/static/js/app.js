document.addEventListener("DOMContentLoaded", () => {

  const toggle = document.getElementById("themeToggle");

  // Load saved theme
  if(localStorage.getItem("theme") === "dark"){
    document.body.classList.add("dark");
    toggle.innerText = "☀️";
  }

  toggle?.addEventListener("click", () => {

    document.body.classList.toggle("dark");

    if(document.body.classList.contains("dark")){
      toggle.innerText = "☀️";
      localStorage.setItem("theme","dark");
    }else{
      toggle.innerText = "🌙";
      localStorage.setItem("theme","light");
    }

  });

});
// ===== MOBILE MENU =====
const menuToggle = document.getElementById("menuToggle");
const navLinks = document.getElementById("navLinks");

menuToggle?.addEventListener("click", () => {
  navLinks.classList.toggle("active");
});
// ===== LOADER FIX =====
window.addEventListener("load", () => {
  const loader = document.getElementById("loader");
  
  setTimeout(() => {
    loader.classList.add("hide");
  }, 800); // delay for smooth effect
});
// ===== AUTO SLIDER =====
let slideIndex = 0;

function autoSlide(){
    const track = document.getElementById("sliderTrack");
    if(!track) return;

    const slides = document.querySelectorAll(".slide");
    const totalSlides = slides.length;

    slideIndex++;

    if(slideIndex >= totalSlides){
        slideIndex = 0;
    }

    track.style.transform = `translateX(-${slideIndex * 100}%)`;
}

setInterval(autoSlide, 4000); // 4 sec
