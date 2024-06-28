const tour = new Shepherd.Tour({
    useModalOverlay: true,
    confirmCancel: true,
    confirmCancelMessage: 'Вы точно хотите завершить? Перезапустить знакомство будет невозможно.',
    defaultStepOptions: {
        classes: 'shadow-md bg-purple-dark',
        scrollTo: true,
        cancelIcon: {
            enabled: true,
            ariaLabel: 'Close this tour',
        },
    },
});

//Step 1
tour.addStep({
    title: '<strong>Добро пожаловать на MP Monitor!</strong>',
    text: 'Сейчас мы ознакомимся:<ul>' +
        '<li>с основными элементами интерфейса</li>' +
        '<li>с тем, как запустить первый парсинг</li>' +
        '<li>с тем, как создать автоматическое расписание</li></ul> ' +
        'Для продолжения нажмите <strong>"Дальше".</strong>',
    buttons: [
        {
            text: 'Отмена',
            action: tour.cancel,
            classes: ['hidden',]
        },
        {
            text: 'Дальше',
            action: tour.next,
        }
    ],
});

// Step 2
tour.addStep({
    title: '<strong>Форма добавления товаров</strong>',
    text: 'Давайте откроем форму для добавления товаров.<br>' +
        'Для продолжения кликните на кнопку <span class="material-symbols-sharp label text-primary">add</span>',
     advanceOn: {
        selector: '#addItemsToggleLink',
        event: 'click',
    },
    attachTo: {
        element: '#addItemsToggle',
        on: 'top',
    },
    buttons: [
        {
            text: 'Назад',
            action: tour.back,
            secondary: true,
        },
        {
            text: 'Дальше',
            action: tour.next,
            disabled: true,
        },
    ],
});

// Step 3
tour.addStep({
    title: '<strong>Форма добавления товаров</strong>',
    text: '<p>Тут мы можем добавить новые товары для парсинга, используя артикулы товаров.</p>' +
        '<p>Для продолжения нажмите <strong>"Дальше"</strong>.</p>',
    attachTo: {
        element: '#addItemsForm',
        on: 'bottom',
    },
    canClickTarget: false, // disable ability to enter info into form and submit
    buttons: [
        {
            text: 'Назад',
            action: tour.back,
            secondary: true,
        },
        {
            text: 'Дальше',
            // click the manual update tab and proceed to the next step
            action: clickManualTabAndProceed(),
        },
    ],
});


// Step 4
tour.addStep({
    title: '<strong>Список товаров</strong>',
    text: 'Здесь находятся все ваши товары, а также:<ul>' +
        '<li>их текущая цена на Wildberries</li>' +
        '<li>разница с предыдущим парсингом</li>' +
        '<li>время последнего парсинга</li></ul>' +
        '<p>Для продолжения нажмите <strong>"Дальше"</strong>.</p>',
    attachTo: {
        element: '#itemsTable',
        on: 'top',
    },
    canClickTarget: false,
    buttons: [
        {
            text: 'Назад',
            action: tour.back,
            secondary: true,
        },
        {
            text: 'Дальше',
            action: tour.next,
            // disabled: true,
        },
    ],
});


// Step 5
tour.addStep({
    title: '<strong>Вкладки обновления товаров</strong>',
    text: '<p>Здесь переключаемся между ручным обновлением и созданием автоматического расписания.</p>' +
        '<p>Покликайте на вкладки, чтобы посмотреть, как это работает.</p>' +
        '<p>Для продолжения нажмите <strong>"Дальше"</strong>.</p>',
    attachTo: {
        element: '#manualAutoTabs',
        on: 'top',
    },
    buttons: [
        {
            text: 'Назад',
            action: clickManualTabAndGoBack(),
            secondary: true,
        },
        {
            text: 'Дальше',
            action: clickManualTabAndProceed(),
        },
    ],
});

// Step 6
tour.addStep({
    title: '<strong>Ручное обновление товаров</strong>',
    text: 'Для получения обновленной информации с Wildberries о выбранных товарах нужно:<br><br>' +
        '<ul>' +
        '<li>выбрать в таблице товары, которые вы хотите парсить</li>' +
        '<li>нажать на кнопку "Обновить вручную"</li>' +
        '</ul>' +
        '<p>Для продолжения нажмите <strong>"Дальше"</strong>.</p>',
    attachTo: {
        element: '#myTabContent',
        on: 'top-start',
    },
    canClickTarget: false,
    buttons: [
        {
            text: 'Назад',
            action: clickManualTabAndGoBack(),
            secondary: true,
        },
        {
            text: 'Дальше',
            action: clickScheduleTabAndProceed(),
        },
    ],
});


// Step 7
tour.addStep({
    title: '<strong>Создание автоматического расписания</strong>',
    text: 'Для создания автоматическогого расписания нужно:<br><br>' +
        '<ul>' +
        '<li>поставить регулярность обновления (напр., каждые 2 часа)</li>' +
        '<li>выбрать в таблице товары, которые вы хотите парсить</li>' +
        '<li>нажать на кнопку "Создать расписание"</li>' +
        '</ul>' +
        '<p>Для продолжения нажмите <strong>"Дальше"</strong>.</p>',
    attachTo: {
        element: '#myTabContent',
        on: 'top-end',
    },
    canClickTarget: false,
    buttons: [
        {
            text: 'Назад',
            action: clickManualTabAndGoBack(),
            secondary: true,
        },
        {
            text: 'Дальше',
            action: tour.next,
        },
    ],
});

// Step 8
tour.addStep({
    title: '<strong>Готово! Что теперь?</strong>',
    text: 'Кликните на артикул в таблице для получения подробной информации о товаре, такую как:<br><br>' +
        '<ul>' +
        '<li>история цен, которые вы парсили</li>' +
        '<li>максимальная, минимальная, текущая и средняя цена товара на Wildberries</li>' +
        '</ul>' +
        '<p>Для завершения нажмите <strong>"Завершить"</strong>.</p>',
    buttons: [
        {
            text: 'Назад',
            action: tour.back,
            secondary: true,
        },
        {
            text: 'Завершить',
            action() {
                dismissTour();
                tour.complete();
            }
        }
    ],
});

// Helper functions

// Display the current step number and total number of steps in the tour footer
function displayProgress() {
    const currentStep = Shepherd.activeTour?.getCurrentStep();
    const currentStepElement = currentStep?.getElement();
    const footer = currentStepElement?.querySelector('.shepherd-footer');
    const progress = document.createElement('span');
    progress.className = 'shepherd-progress';
    progress.innerText = `${Shepherd.activeTour?.steps.indexOf(currentStep) + 1} из ${Shepherd.activeTour?.steps.length}`;
    footer?.insertBefore(progress, currentStepElement.querySelector('.shepherd-button:last-child'));
}

// Ensure that user is on the correct tab before proceeding to the next step
function clickManualTabAndProceed() {
    return function () {
        const manualUpdateTab = document.querySelector('#manual-update-tab');
        manualUpdateTab.click();
        tour.next();
    };
}

function clickManualTabAndGoBack() {
    return function () {
        const manualUpdateTab = document.querySelector('#manual-update-tab');
        manualUpdateTab.click();
        tour.back();
    };
}

function clickScheduleTabAndProceed() {
    return function () {
        const scheduleUpdateTab = document.querySelector('#schedule-update-tab');
        scheduleUpdateTab.click();
        tour.next();
    };
}

// run displayProgress() function for each step when show event is fired
for (const step of tour.steps) {
    step.on('show', function () {
        displayProgress();
    });
}


// check the browser's localstorage
function dismissTour(){
    if(!localStorage.getItem('demo-tour')) {
        localStorage.setItem('demo-tour', 'yes');
    }
}

// Dismiss the tour when the cancel icon is clicked. Do not show the tour on next page reload
tour.on('cancel', dismissTour);

// Initiate the tour only if localstorage does not contain demo-tour and user is on the item_list page
// This ensures that the tour is only shown once per user
if(!localStorage.getItem('demo-tour') && window.location.pathname.includes('/item_list/')) {
    // wait 1 second before showing the tour
    setTimeout(() => {
        tour.start();
    }, 1000);
}
