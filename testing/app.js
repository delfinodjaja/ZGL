// Ensure Chart.js is loaded
if (typeof Chart !== 'undefined') {
  // Chart.js Initialization
  Chart.defaults.global.defaultFontFamily = 'Plus Jakarta Sans', sans-serif;
  Chart.defaults.global.defaultFontSize = 14;
  Chart.defaults.global.defaultFontColor = '#F8FAFC';
  Chart.defaults.global.elements.line.tension = 0.4;
  Chart.defaults.global.elements.line.fill = true;
  Chart.defaults.global.elements.line.backgroundColor = 'rgba(59, 130, 246, 0.2)';
  Chart.defaults.global.elements.line.borderColor = '#3B82F6';
  Chart.defaults.global.elements.line.borderWidth = 2;
  Chart.defaults.global.elements.point.radius = 4;
  Chart.defaults.global.elements.point.backgroundColor = '#3B82F6';
  Chart.defaults.global.elements.point.borderColor = '#fff';
  Chart.defaults.global.tooltips.backgroundColor = '#161C28';
  Chart.defaults.global.tooltips.cornerRadius = 4;
  Chart.defaults.global.tooltips.bodyFontColor = '#F8FAFC';
  Chart.defaults.global.tooltips.titleFontColor = '#F8FAFC';

  // Render #revenueChart
  const revenueData = {
    labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'],
    datasets: [
      {
        label: 'Revenue vs Target',
        data: [120, 150, 180, 210, 240, 270, 300],
        fill: true,
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        borderColor: '#3B82F6',
        borderWidth: 2
      }
    ]
  };
  const revenueChart = new Chart(document.getElementById('revenueChart'), {
    type: 'line',
    data: revenueData,
    options: {
      scales: {
        yAxes: [{
          ticks: {
            beginAtZero: true
          }
        }]
      }
    }
  });

  // Render #categoryChart
  const categoryData = {
    labels: ['Electronics', 'Clothing', 'Home', 'Toys'],
    datasets: [
      {
        data: [30, 25, 40, 15],
        backgroundColor: ['#FF6B6B', '#87CEEB', '#9ACD32', '#FFA500']
      }
    ]
  };
  const categoryChart = new Chart(document.getElementById('categoryChart'), {
    type: 'doughnut',
    data: categoryData,
    options: {
      cutoutPercentage: 40,
      offsetRadius: 10
    }
  });

  // Render mini sparkline line charts inside the top KPI cards
  function renderSparkline(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: ['Jan', 'Feb', 'Mar'],
        datasets: [
          {
            data: data,
            fill: false,
            borderColor: '#3B82F6',
            borderWidth: 1
          }
        ]
      },
      options: {
        scales: {
          yAxes: [{
            ticks: {
              display: false
            }
          }],
          xAxes: [{
            ticks: {
              display: false
            }
          }]
        }
      }
    });
  }

  renderSparkline('revenueSparkline', [120, 150, 180]);
  renderSparkline('orderValueSparkline', [1200, 1300, 1400]);
  renderSparkline('conversionRateSparkline', [15, 16, 17]);
  renderSparkline('dealsSparkline', [120, 130, 140]);

  // UI Interactivity
  const searchBar = document.querySelector('.search-bar');
  const dataTableBody = document.querySelector('#data-table-section tbody');
  const filterButton = document.querySelector('.filter-button');
  const navLinks = document.querySelectorAll('nav a');
  const sidebarToggle = document.querySelector('aside');
  const mainContent = document.querySelector('main');

  searchBar.addEventListener('input', () => {
    const searchTerm = searchBar.value.toLowerCase();
    dataTableBody.innerHTML = '';
    // Fetch and filter data based on searchTerm
  });

  filterButton.addEventListener('click', () => {
    // Implement filter logic
  });

  navLinks.forEach(link => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      navLinks.forEach(a => a.classList.remove('active'));
      link.classList.add('active');
      // Fetch and display data for the selected section
    });
  });

  sidebarToggle.addEventListener('click', () => {
    sidebarToggle.classList.toggle('collapsed');
    mainContent.classList.toggle('shifted');
  });
} else {
  console.error('Chart.js is not loaded. Please ensure it is included correctly in your HTML file.');
}